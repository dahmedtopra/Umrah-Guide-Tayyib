import json
import logging
import os
import time
from typing import Any, Dict, List

import requests

from app.db.sqlite import insert_analytics
from app.schemas.ask import AnswerBlock, AskRequest, AskResponse, SourceItem
from app.services.hash_service import hash_query
from app.services.offline_pack_service import get_suggestions, match_offline
from app.services.rag_service import retrieve

OFFLINE_THRESHOLD = 0.25
RAG_THRESHOLD = 0.35
MIN_SOURCES = 1
MIN_SOURCE_SCORE = 0.2

_last_openai_error = {"code": "", "message": ""}


def _event_mode() -> bool:
  return os.getenv("EVENT_MODE", "false").lower() in ("1", "true", "yes")


def _log_info(message: str, *args: Any) -> None:
  if not _event_mode():
    logging.info(message, *args)


def _set_openai_error(code: str, message: str) -> None:
  global _last_openai_error
  _last_openai_error = {"code": code[:50], "message": message[:200]}


def get_last_openai_error() -> Dict[str, str]:
  return _last_openai_error


def safe_response() -> AskResponse:
  return AskResponse(
    answer=AnswerBlock(direct="", steps=[], mistakes=[]),
    sources=[],
    confidence=0.0,
    refinement_chips=[],
    route_used="fallback",
    latency_ms=0,
    clarifying_question="I couldn't complete that request. Please try again or rephrase.",
    error_code="ask_error",
    error_message="The request could not be completed.",
    debug_notes="fallback: exception",
  )


def clarifier(query: str, lang: str) -> str:
  q = (query or "").lower()
  if lang == "AR":
    if "الإحرام" in query or "ihram" in q:
      return "هل تقصد أحكام الإحرام، أم عبور الميقات، أم ماذا تفعل إذا تجاوزت الميقات؟"
    if "الروضة" in query or "rawdah" in q:
      return "هل تقصد حجز الروضة الشريفة أم قواعد الزيارة؟"
    return "هل تقصد خطوة من خطوات العمرة، أم تصريح نسك، أم زيارة الروضة الشريفة؟"
  if lang == "FR":
    if "ihram" in q:
      return "Parlez-vous des regles de l'ihram, du passage du miqat, ou de quoi faire apres l'avoir depasse ?"
    if "rawdah" in q:
      return "Parlez-vous de la reservation Rawdah ou des regles de visite ?"
    return "Parlez-vous d'une etape de la Omra, d'un permis Nusuk, ou de la Rawdah ?"
  if "ihram" in q:
    return "Do you mean ihram rules, crossing the miqat, or what to do if you already passed miqat?"
  if "rawdah" in q:
    return "Do you mean Rawdah booking or visit rules?"
  return "Do you mean an Umrah step, a Nusuk permit, or Rawdah visit details?"


def clarifier_options(query: str, lang: str) -> List[str]:
  q = (query or "").lower()
  if lang == "AR":
    if "الإحرام" in query or "ihram" in q:
      return ["أحكام الإحرام", "عبور الميقات", "تجاوز الميقات"]
    if "الروضة" in query or "rawdah" in q:
      return ["حجز الروضة الشريفة", "قواعد الزيارة", "وقت التصريح"]
    return ["خطوات العمرة", "تصريح نسك", "زيارة الروضة الشريفة"]
  if lang == "FR":
    if "ihram" in q:
      return ["Regles de l'ihram", "Passage du miqat", "Depassement du miqat"]
    if "rawdah" in q:
      return ["Reservation Rawdah", "Regles de visite", "Heure du permis"]
    return ["Etapes de la Omra", "Permis Nusuk", "Visite Rawdah"]
  if "ihram" in q:
    return ["Ihram rules", "Miqat crossing", "Passed miqat"]
  if "rawdah" in q:
    return ["Rawdah booking", "Visit rules", "Permit timing"]
  return ["Umrah steps", "Nusuk permit", "Rawdah visit"]


def is_out_of_scope(query: str) -> bool:
  q = (query or "").lower()
  keywords = [
    "visa",
    "immigration",
    "passport",
    "medical",
    "vaccine",
    "health",
    "legal",
    "law",
    "lawsuit",
    "court",
    "hajj only",
    "hajj",
    "umrah visa",
    "employment",
  ]
  return any(k in q for k in keywords)


def out_of_scope_message(lang: str) -> str:
  if lang == "AR":
    return "هذا الكشك مخصص لإرشادات العمرة ونسك والروضة الشريفة فقط."
  if lang == "FR":
    return "Ce kiosque couvre uniquement la Omra, Nusuk et la Rawdah."
  return "This kiosk covers Umrah, Nusuk, and Rawdah guidance only."


def suggestion_chips(query: str, lang: str) -> List[str]:
  chips = get_suggestions(query, lang, limit=3)
  return chips if chips else clarifier_options(query, lang)


def build_prompt(query: str, lang: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  snippets = "\n\n".join(
    f"Title: {s.get('title', '')}\nURL: {s.get('url_or_path', '')}\nSnippet: {s.get('snippet', '')}"
    for s in sources
  )
  system_text = (
    "You are a kiosk assistant. Use only the provided snippets. "
    "Avoid madhhab comparisons. Be informational, not a fatwa. "
    "Return concise blocks suitable for a kiosk."
  )
  user_text = (
    f"Language: {lang}\n"
    f"Question: {query}\n"
    f"Snippets:\n{snippets}\n\n"
    "Return JSON only."
  )
  return [
    {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
    {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
  ]


def build_prompt_ungrounded(query: str, lang: str) -> List[Dict[str, Any]]:
  system_text = (
    "You are a kiosk assistant. Provide cautious, general guidance when official sources are unavailable. "
    "Avoid madhhab comparisons. Be informational, not a fatwa. "
    "Do not invent citations or claim a source. "
    "Return concise blocks suitable for a kiosk."
  )
  user_text = (
    f"Language: {lang}\n"
    f"Question: {query}\n"
    "Include this exact disclaimer in the direct answer: "
    "\"General guidance (not sourced from the official PDFs). Please verify in Nusuk/official channels for critical details.\" "
    "Return JSON only."
  )
  return [
    {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
    {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
  ]


def build_prompt_clarify(query: str, lang: str) -> List[Dict[str, Any]]:
  system_text = (
    "You are a kiosk assistant. Ask one concise clarifying question to narrow the user's intent. "
    "Provide 3 short button options that are likely interpretations. "
    "Do not include citations. Keep it brief and relevant."
  )
  user_text = f"Language: {lang}\nUser question: {query}\nReturn JSON only."
  return [
    {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
    {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
  ]


CLARIFY_SCHEMA = {
  "type": "object",
  "additionalProperties": False,
  "properties": {
    "clarifying_question": {"type": "string"},
    "refinement_chips": {"type": "array", "items": {"type": "string"}},
  },
  "required": ["clarifying_question", "refinement_chips"],
}


def call_responses_api(
  messages: List[Dict[str, Any]],
  schema: Dict[str, Any] | None = None,
  schema_name: str = "kiosk_answer",
) -> Dict[str, Any]:
  api_key = os.getenv("OPENAI_API_KEY")
  if not api_key:
    raise RuntimeError("OPENAI_API_KEY missing")

  model = os.getenv("OPENAI_MODEL", "gpt-4o")
  url = "https://api.openai.com/v1/responses"
  headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
  }

  if schema is None:
    schema = {
      "type": "object",
      "additionalProperties": False,
      "properties": {
        "answer": {
          "type": "object",
          "additionalProperties": False,
          "properties": {
            "direct": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
            "mistakes": {"type": "array", "items": {"type": "string"}},
          },
          "required": ["direct", "steps", "mistakes"],
        },
        "refinement_chips": {"type": "array", "items": {"type": "string"}},
      },
      "required": ["answer", "refinement_chips"],
    }

  payload = {
    "model": model,
    "input": messages,
    "text": {
      "format": {
        "type": "json_schema",
        "name": schema_name,
        "schema": schema,
        "strict": True,
      }
    },
  }

  last_err: Exception | None = None
  for attempt in range(2):
    try:
      _log_info("openai_start")
      resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=(5, 12))
      if resp.status_code == 429 or resp.status_code >= 500:
        raise RuntimeError(f"openai_http_{resp.status_code}")
      resp.raise_for_status()
      _log_info("openai_success")
      return resp.json()
    except Exception as e:
      last_err = e
      _set_openai_error(type(e).__name__, str(e))
      if not _event_mode():
        logging.warning("openai_error %s", type(e).__name__)
      if attempt == 0:
        time.sleep(0.6)
        continue
  raise last_err or RuntimeError("OpenAI call failed")


def extract_output_text(data: Dict[str, Any]) -> str:
  if isinstance(data.get("output_text"), str):
    return data["output_text"]
  output = data.get("output", [])
  parts: List[str] = []
  for item in output:
    for c in item.get("content", []):
      if c.get("type") in ("output_text", "text"):
        parts.append(c.get("text", ""))
  return "\n".join(parts)


def to_sources(items: List[Dict[str, Any]]) -> List[SourceItem]:
  return [
    SourceItem(
      title=s.get("title", ""),
      url=s.get("url_or_path", ""),
      snippet=s.get("snippet", ""),
      relevance=s.get("relevance", "Low"),
      page=s.get("page"),
      page_label=s.get("page_label"),
      page_start=s.get("page_start"),
      page_end=s.get("page_end"),
    )
    for s in items
  ]


def _parse_answer(output_text: str) -> tuple[str, List[str], List[str], List[str]]:
  parsed = json.loads(output_text)
  answer = parsed.get("answer", {}) if isinstance(parsed, dict) else {}
  chips = parsed.get("refinement_chips", []) if isinstance(parsed, dict) else []
  direct = answer.get("direct", "") if isinstance(answer, dict) else ""
  steps_val = answer.get("steps", []) if isinstance(answer, dict) else []
  mistakes_val = answer.get("mistakes", []) if isinstance(answer, dict) else []
  if not direct and steps_val:
    direct = steps_val[0]
  return direct, steps_val, mistakes_val, chips if isinstance(chips, list) else []


def answer_query(payload: AskRequest) -> AskResponse:
  start = time.time()
  response = safe_response()
  original_query = payload.query or ""
  rag_conf = 0.0

  try:
    clarify_choice = payload.clarifier_choice or ""
    effective_query = (
      f"{original_query}\nClarifier choice: {clarify_choice}"
      if payload.clarified and clarify_choice
      else original_query
    )

    if is_out_of_scope(original_query) and not payload.clarified:
      response = AskResponse(
        answer=AnswerBlock(direct="", steps=[], mistakes=[]),
        sources=[],
        confidence=0.0,
        refinement_chips=suggestion_chips(original_query, payload.lang),
        route_used="fallback",
        latency_ms=0,
        clarifying_question=out_of_scope_message(payload.lang),
        debug_notes="fallback: out_of_scope",
      )
      _log_info("branch=fallback out_of_scope=true")
    else:
      match, confidence = match_offline(effective_query, payload.lang)
      if match and confidence >= OFFLINE_THRESHOLD:
        source_ids = match.get("source_ids", [])
        sources, _ = retrieve(effective_query, payload.lang, top_k=3)
        filtered = [s for s in sources if s.get("source_id") in source_ids and s.get("score", 0) >= MIN_SOURCE_SCORE]
        if len(filtered) >= MIN_SOURCES:
          answer = match.get("answer", {})
          response = AskResponse(
            answer=AnswerBlock(
              direct=answer.get("direct", ""),
              steps=answer.get("steps", []),
              mistakes=answer.get("mistakes", []),
            ),
            sources=to_sources(filtered),
            confidence=confidence,
            refinement_chips=[],
            route_used="offline",
            latency_ms=0,
          )
          _log_info("branch=offline sources=%d", len(filtered))

      if response.route_used != "offline":
        sources, rag_conf = retrieve(effective_query, payload.lang, top_k=5)
        sources = [s for s in sources if s.get("score", 0) >= MIN_SOURCE_SCORE]
        weak_rag = len(sources) < MIN_SOURCES or rag_conf < RAG_THRESHOLD

        if weak_rag:
          if payload.clarified:
            try:
              data = call_responses_api(build_prompt_ungrounded(effective_query, payload.lang))
              direct, steps_val, mistakes_val, refinement = _parse_answer(extract_output_text(data))
              if not direct:
                response = AskResponse(
                  answer=AnswerBlock(direct="", steps=[], mistakes=[]),
                  sources=[],
                  confidence=0.0,
                  refinement_chips=suggestion_chips(original_query, payload.lang),
                  route_used="fallback",
                  latency_ms=0,
                  clarifying_question=None,
                  debug_notes="fallback: clarified_no_answer",
                )
              else:
                response = AskResponse(
                  answer=AnswerBlock(direct=direct, steps=steps_val, mistakes=mistakes_val),
                  sources=[],
                  confidence=0.0,
                  refinement_chips=refinement,
                  route_used="general",
                  latency_ms=0,
                  error_code="ungrounded_llm",
                  error_message="No sources found; generated general guidance",
                  debug_notes="general: clarified_no_sources",
                  general_mode=True,
                )
              _log_info("branch=general clarified=true sources=0")
            except Exception as e:
              msg = str(e).lower()
              if "openai_api_key" in msg or "missing" in msg:
                debug = "fallback: openai_missing_key"
              elif "timeout" in msg:
                debug = "fallback: openai_timeout"
              else:
                debug = "fallback: openai_error"
              response = AskResponse(
                answer=AnswerBlock(direct="Service unavailable. Please try again.", steps=[], mistakes=[]),
                sources=[],
                confidence=0.0,
                refinement_chips=suggestion_chips(original_query, payload.lang),
                route_used="fallback",
                latency_ms=0,
                clarifying_question=None,
                error_code="openai_unavailable",
                error_message="LLM step unavailable; using clarifier",
                debug_notes=debug,
              )
              _log_info("branch=fallback openai_error")
          else:
            try:
              data = call_responses_api(
                build_prompt_clarify(original_query, payload.lang),
                schema=CLARIFY_SCHEMA,
                schema_name="kiosk_clarify",
              )
              parsed = json.loads(extract_output_text(data))
              llm_question = parsed.get("clarifying_question", "")
              llm_chips = parsed.get("refinement_chips", [])
              if not isinstance(llm_question, str) or not llm_question.strip():
                raise RuntimeError("clarify_missing_question")
              if not isinstance(llm_chips, list) or not llm_chips:
                llm_chips = suggestion_chips(payload.query, payload.lang)
              response = AskResponse(
                answer=AnswerBlock(direct="", steps=[], mistakes=[]),
                sources=[],
                confidence=rag_conf,
                refinement_chips=llm_chips[:3],
                route_used="fallback",
                latency_ms=0,
                clarifying_question=llm_question.strip(),
                debug_notes="fallback: rag_low_clarify_llm",
              )
              _log_info("branch=fallback clarify_llm sources=0")
            except Exception:
              response = AskResponse(
                answer=AnswerBlock(direct="", steps=[], mistakes=[]),
                sources=[],
                confidence=rag_conf,
                refinement_chips=suggestion_chips(original_query, payload.lang),
                route_used="fallback",
                latency_ms=0,
                clarifying_question=clarifier(original_query, payload.lang),
                debug_notes="fallback: rag_empty",
              )
              _log_info("branch=fallback rag_empty sources=0")
        else:
          try:
            data = call_responses_api(build_prompt(effective_query, payload.lang, sources))
            direct, steps_val, mistakes_val, refinement = _parse_answer(extract_output_text(data))
            response = AskResponse(
              answer=AnswerBlock(direct=direct, steps=steps_val, mistakes=mistakes_val),
              sources=to_sources(sources),
              confidence=rag_conf,
              refinement_chips=refinement,
              route_used="rag",
              latency_ms=0,
            )
            if not direct and not steps_val and not mistakes_val:
              response = AskResponse(
                answer=AnswerBlock(direct="", steps=[], mistakes=[]),
                sources=[],
                confidence=rag_conf,
                refinement_chips=suggestion_chips(original_query, payload.lang),
                route_used="fallback",
                latency_ms=0,
                clarifying_question=clarifier(original_query, payload.lang),
                debug_notes="fallback: empty_answer",
              )
            elif len(response.sources) < MIN_SOURCES:
              response = AskResponse(
                answer=AnswerBlock(direct="", steps=[], mistakes=[]),
                sources=[],
                confidence=rag_conf,
                refinement_chips=clarifier_options(original_query, payload.lang),
                route_used="fallback",
                latency_ms=0,
                clarifying_question=clarifier(original_query, payload.lang),
                debug_notes="fallback: sources_empty",
              )
            _log_info("branch=rag sources=%d", len(sources))
          except Exception as e:
            msg = str(e).lower()
            if "openai_api_key" in msg or "missing" in msg:
              debug = "fallback: openai_missing_key"
            elif "timeout" in msg:
              debug = "fallback: openai_timeout"
            else:
              debug = "fallback: openai_error"
            response = AskResponse(
              answer=AnswerBlock(direct="", steps=[], mistakes=[]),
              sources=[],
              confidence=rag_conf,
              refinement_chips=suggestion_chips(original_query, payload.lang),
              route_used="fallback",
              latency_ms=0,
              clarifying_question=clarifier(original_query, payload.lang),
              error_code="openai_unavailable",
              error_message="LLM step unavailable; using clarifier",
              debug_notes=debug,
            )
  except Exception:
    logging.exception("/api/ask failed")
    response = safe_response()
  finally:
    latency_ms = int((time.time() - start) * 1000)
    response.latency_ms = latency_ms
    try:
      insert_analytics(
        session_id=payload.session_id,
        mode="ask",
        lang=payload.lang,
        rating_1_5=None,
        time_on_screen_ms=None,
        route_used=response.route_used,
        confidence=response.confidence,
        sources_count=len(response.sources) if response.sources else 0,
        error_code=response.error_code,
        latency_ms=latency_ms,
        hashed_query=hash_query(original_query),
      )
    except Exception:
      pass

  return response
