import json
import os
import time
import logging
from typing import Any, Dict, Generator, List

import requests

from app.schemas.chat import ChatRequest, ChatSourceItem, ChatResponseMeta
from app.db.sqlite import insert_analytics
from app.services.hash_service import hash_query
from app.services.offline_pack_service import match_offline, get_suggestions
from app.services.rag_service import retrieve
from app.services.ask_service import (
  is_out_of_scope,
  out_of_scope_message,
  suggestion_chips,
)

OFFLINE_THRESHOLD = 0.25
RAG_THRESHOLD = 0.35
MIN_SOURCES = 1
MIN_SOURCE_SCORE = 0.2
MAX_HISTORY_MESSAGES = 10

# Question words that signal the query is a clear question, not vague
_QUESTION_WORDS = {
    "how", "what", "where", "when", "why", "who", "which",
    "can", "does", "do", "is", "are", "should", "will", "tell",
}


def _is_vague_query(query: str) -> bool:
    """Return True when the query is too short/vague to answer directly."""
    q = query.strip()
    words = q.split()
    if len(words) >= 4:
        return False
    if "?" in q:
        return False
    first = words[0].lower().rstrip("?") if words else ""
    if first in _QUESTION_WORDS:
        return False
    return True


def _effective_query(messages, latest_query: str) -> str:
    """Combine the original question with a clarifier follow-up for better RAG retrieval."""
    user_messages = [m for m in messages if m.role == "user"]
    if len(user_messages) >= 2:
        original = user_messages[-2].content
        if original.lower().strip() != latest_query.lower().strip():
            return f"{original} ({latest_query})"
    return latest_query


def _sse_token(text: str) -> str:
  return f"event: token\ndata: {text}\n\n"


def _sse_meta(meta: ChatResponseMeta) -> str:
  return f"event: meta\ndata: {meta.model_dump_json()}\n\n"


def _to_chat_sources(items: List[Dict[str, Any]]) -> List[ChatSourceItem]:
  return [
    ChatSourceItem(
      title=s.get("title", ""),
      url=s.get("url_or_path", s.get("url", "")),
      snippet=s.get("snippet", ""),
      relevance=s.get("relevance", "Low"),
      page=s.get("page"),
      page_label=s.get("page_label"),
      page_start=s.get("page_start"),
      page_end=s.get("page_end"),
    )
    for s in items
  ]


def _build_system_prompt(lang: str, sources: List[Dict[str, Any]] | None = None) -> str:
  lang_name = {"EN": "English", "AR": "Arabic", "FR": "French"}.get(lang, "English")

  base = (
    f"You are Tayyib, a friendly and knowledgeable Umrah assistant on a public kiosk. "
    f"You help pilgrims with Umrah steps, Nusuk permits, Rawdah visits, and related guidance.\n\n"
    f"Rules:\n"
    f"- Respond in {lang_name}.\n"
    f"- Be conversational but concise. This is a kiosk — people are standing.\n"
    f"- Do not give fatwas. Do not compare madhahib.\n"
    f"- Be informational and compassionate.\n"
    f"- If you reference a source, cite it as [Source N] inline.\n"
    f"- If you don't know something, say so honestly.\n"
    f"- Do not invent citations.\n"
    f"- Keep responses under 200 words unless the user asks for detail.\n\n"
    f"FORMATTING (you MUST follow this exactly):\n"
    f"- Use markdown. Put each heading, bullet, and paragraph on its OWN line.\n"
    f"- Always put a BLANK LINE before every ## heading.\n"
    f"- Always put each bullet (- ) on its own line.\n"
    f"- Use only these sections (skip any that don't apply):\n"
    f"  ## Direct Answer\n"
    f"  ## Steps\n"
    f"  ## Common Mistakes\n"
    f"- Keep bullets short and practical.\n"
    f"- For simple questions, just use ## Direct Answer with a short paragraph — skip Steps/Mistakes.\n\n"
    f"Example of correct formatting:\n\n"
    f"## Direct Answer\n"
    f"Tawaf is the act of circling the Kaaba seven times.\n\n"
    f"## Steps\n"
    f"- Start from the Black Stone corner\n"
    f"- Walk counter-clockwise around the Kaaba\n"
    f"- Complete seven full circuits\n\n"
    f"## Common Mistakes\n"
    f"- Not starting from the correct corner\n"
    f"- Miscounting the number of circuits\n"
  )

  if sources:
    snippets = "\n\n".join(
      f"[Source {i+1}] Title: {s.get('title','')}\nURL: {s.get('url_or_path','')}\nSnippet: {s.get('snippet','')}"
      for i, s in enumerate(sources)
    )
    base += f"\nAvailable sources:\n{snippets}\n"

  return base


def _build_system_prompt_ungrounded(lang: str) -> str:
  lang_name = {"EN": "English", "AR": "Arabic", "FR": "French"}.get(lang, "English")
  return (
    f"You are Tayyib, a friendly Umrah assistant on a public kiosk. "
    f"No official sources are available for this question. Provide cautious, general guidance.\n\n"
    f"Rules:\n"
    f"- Respond in {lang_name}.\n"
    f"- Be conversational but concise.\n"
    f"- Do not give fatwas. Do not compare madhahib.\n"
    f"- Do not invent citations or claim a source.\n"
    f"- Start your response with: \"I don't have official sources for this, but here's general guidance:\"\n"
    f"- Keep responses under 200 words.\n\n"
    f"FORMATTING (you MUST follow this exactly):\n"
    f"- Use markdown. Put each heading, bullet, and paragraph on its OWN line.\n"
    f"- Always put a BLANK LINE before every ## heading.\n"
    f"- Always put each bullet (- ) on its own line.\n"
    f"- Use only these sections (skip any that don't apply):\n"
    f"  ## Direct Answer\n"
    f"  ## Steps\n"
    f"  ## Common Mistakes\n"
    f"- For simple questions, just use ## Direct Answer with a short paragraph.\n"
  )


def _build_openai_input(
  system_prompt: str,
  history: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
  messages: List[Dict[str, Any]] = [
    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]}
  ]
  for msg in history:
    role = msg["role"]
    if role == "assistant":
      messages.append({
        "role": "assistant",
        "content": [{"type": "output_text", "text": msg["content"]}],
      })
    else:
      messages.append({
        "role": "user",
        "content": [{"type": "input_text", "text": msg["content"]}],
      })
  return messages


def _offline_to_prose(match: Dict[str, Any], lang: str) -> str:
  answer = match.get("answer", {})
  parts: List[str] = []

  if answer.get("direct"):
    if lang == "AR":
      parts.append("## ??????? ????????")
    elif lang == "FR":
      parts.append("## Reponse directe")
    else:
      parts.append("## Direct Answer")
    parts.append(answer["direct"])

  steps = answer.get("steps", [])
  if steps:
    if lang == "AR":
      parts.append("## ???????")
    elif lang == "FR":
      parts.append("## Etapes")
    else:
      parts.append("## Steps")
    parts.append("\n".join(f"- {s}" for s in steps))

  mistakes = answer.get("mistakes", [])
  if mistakes:
    if lang == "AR":
      parts.append("## ????? ????? ??? ??????")
    elif lang == "FR":
      parts.append("## Erreurs courantes a eviter")
    else:
      parts.append("## Common Mistakes")
    parts.append("\n".join(f"- {m}" for m in mistakes))

  return "\n\n".join(parts)


def _yield_text_as_tokens(text: str, chunk_size: int = 8) -> Generator[str, None, None]:
  """Yield text in small chunks to simulate streaming."""
  for i in range(0, len(text), chunk_size):
    yield _sse_token(text[i:i + chunk_size])


def _stream_openai(
  messages: List[Dict[str, Any]],
) -> Generator[str, None, str]:
  """Call OpenAI Responses API with streaming. Yields SSE token events. Returns full text."""
  api_key = os.getenv("OPENAI_API_KEY")
  if not api_key:
    raise RuntimeError("OPENAI_API_KEY missing")

  model = os.getenv("OPENAI_MODEL", "gpt-4o")
  url = "https://api.openai.com/v1/responses"
  headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
  }
  payload = {
    "model": model,
    "input": messages,
    "stream": True,
  }

  full_text = ""
  last_err = None
  for attempt in range(2):
    try:
      resp = requests.post(
        url, headers=headers, data=json.dumps(payload),
        timeout=(5, 30), stream=True,
      )
      if resp.status_code in (429,) or resp.status_code >= 500:
        raise RuntimeError(f"openai_http_{resp.status_code}")
      resp.raise_for_status()

      for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
          continue
        data_str = line[len("data:"):].strip()
        if data_str == "[DONE]":
          break
        try:
          event = json.loads(data_str)
        except json.JSONDecodeError:
          continue

        event_type = event.get("type", "")
        if event_type == "response.output_text.delta":
          delta = event.get("delta", "")
          if delta:
            full_text += delta
            yield _sse_token(delta)

      return full_text
    except Exception as e:
      last_err = e
      logging.warning("openai_stream_error attempt=%d %s", attempt, type(e).__name__)
      if attempt == 0:
        import time as _t
        _t.sleep(0.6)
        continue

  raise last_err or RuntimeError("OpenAI streaming failed")


def stream_chat_response(payload: ChatRequest) -> Generator[str, None, None]:
  start = time.time()
  route_used = "fallback"
  confidence = 0.0
  sources_list: List[Dict[str, Any]] = []
  refinement_chips: List[str] = []
  clarifying_question = None
  general_mode = None
  error_code = None
  latest_query = ""

  try:
    if not payload.messages:
      yield from _yield_text_as_tokens("Please ask me a question about Umrah!")
      route_used = "fallback"
      yield _sse_meta(ChatResponseMeta(
        sources=[], confidence=0.0, refinement_chips=[],
        route_used="fallback", latency_ms=0,
      ))
      return

    # Extract latest user message
    latest_msg = None
    for msg in reversed(payload.messages):
      if msg.role == "user":
        latest_msg = msg
        break
    if not latest_msg:
      yield from _yield_text_as_tokens("Please ask me a question about Umrah!")
      yield _sse_meta(ChatResponseMeta(
        sources=[], confidence=0.0, refinement_chips=[],
        route_used="fallback", latency_ms=0,
      ))
      return

    latest_query = latest_msg.content
    # Build a richer query for retrieval when following up a clarifier
    rag_query = _effective_query(payload.messages, latest_query)

    # Check out-of-scope
    if is_out_of_scope(latest_query):
      oos_msg = out_of_scope_message(payload.lang)
      yield from _yield_text_as_tokens(oos_msg)
      chips = suggestion_chips(latest_query, payload.lang)
      latency_ms = int((time.time() - start) * 1000)
      yield _sse_meta(ChatResponseMeta(
        sources=[], confidence=0.0, refinement_chips=chips,
        route_used="fallback", latency_ms=latency_ms,
      ))
      _log_analytics(payload, "fallback", 0.0, 0, None, latency_ms, latest_query)
      return

    # Try offline match
    match, offline_conf = match_offline(rag_query, payload.lang)
    if match and offline_conf >= OFFLINE_THRESHOLD:
      source_ids = match.get("source_ids", [])
      sources_raw, _ = retrieve(rag_query, payload.lang, top_k=3)
      filtered = [s for s in sources_raw if s.get("source_id") in source_ids and s.get("score", 0) >= MIN_SOURCE_SCORE]
      if len(filtered) >= MIN_SOURCES:
        prose = _offline_to_prose(match, payload.lang)
        yield from _yield_text_as_tokens(prose)
        latency_ms = int((time.time() - start) * 1000)
        yield _sse_meta(ChatResponseMeta(
          sources=_to_chat_sources(filtered),
          confidence=offline_conf,
          refinement_chips=[],
          route_used="offline",
          latency_ms=latency_ms,
        ))
        _log_analytics(payload, "offline", offline_conf, len(filtered), None, latency_ms, latest_query)
        return
      else:
        match = None

    # RAG retrieval
    sources_raw, rag_conf = retrieve(rag_query, payload.lang, top_k=5)
    sources_raw = [s for s in sources_raw if s.get("score", 0) >= MIN_SOURCE_SCORE]
    confidence = rag_conf

    # Truncate conversation history
    history = [{"role": m.role, "content": m.content} for m in payload.messages[-MAX_HISTORY_MESSAGES:]]

    if len(sources_raw) >= MIN_SOURCES and rag_conf >= RAG_THRESHOLD:
      # Grounded RAG response
      system_prompt = _build_system_prompt(payload.lang, sources_raw)
      openai_input = _build_openai_input(system_prompt, history)
      full_text = yield from _stream_openai(openai_input)
      sources_list = sources_raw
      route_used = "rag"

      # Generate refinement chips from LLM response context
      chips = get_suggestions(latest_query, payload.lang, limit=3)
      refinement_chips = chips if chips else []

    else:
      # Weak/no sources — only ask a clarifier if the query is genuinely vague
      # AND it's the very first message. Otherwise, answer with general guidance.
      is_first_message = len(payload.messages) <= 1
      if is_first_message and _is_vague_query(latest_query):
        # Very short/vague first query (e.g. "ihram", "tawaf") — ask clarifier
        clarify_text = (
          "I'd like to help you with that! Could you tell me a bit more about what you're looking for?"
        )
        yield from _yield_text_as_tokens(clarify_text)
        chips = suggestion_chips(latest_query, payload.lang)
        refinement_chips = chips
        route_used = "fallback"
        clarifying_question = clarify_text
      else:
        # Clear question or follow-up — answer with general guidance + disclaimer
        system_prompt = _build_system_prompt_ungrounded(payload.lang)
        openai_input = _build_openai_input(system_prompt, history)
        full_text = yield from _stream_openai(openai_input)
        route_used = "general"
        general_mode = True
        chips = get_suggestions(latest_query, payload.lang, limit=3)
        refinement_chips = chips if chips else []

    latency_ms = int((time.time() - start) * 1000)
    yield _sse_meta(ChatResponseMeta(
      sources=_to_chat_sources(sources_list),
      confidence=confidence,
      refinement_chips=refinement_chips,
      route_used=route_used,
      latency_ms=latency_ms,
      clarifying_question=clarifying_question,
      general_mode=general_mode,
      error_code=error_code,
    ))
    _log_analytics(payload, route_used, confidence, len(sources_list), error_code, latency_ms, latest_query)

  except Exception as e:
    logging.exception("chat stream error")
    error_msg = "I'm sorry, I couldn't complete that request. Please try again."
    yield from _yield_text_as_tokens(error_msg)
    latency_ms = int((time.time() - start) * 1000)
    yield _sse_meta(ChatResponseMeta(
      sources=[], confidence=0.0, refinement_chips=[],
      route_used="fallback", latency_ms=latency_ms,
      error_code="chat_error",
    ))
    _log_analytics(payload, "fallback", 0.0, 0, "chat_error", latency_ms, latest_query)


def _log_analytics(
  payload: ChatRequest,
  route_used: str,
  confidence: float,
  sources_count: int,
  error_code: str | None,
  latency_ms: int,
  query: str,
) -> None:
  try:
    insert_analytics(
      session_id=payload.session_id,
      mode="chat",
      lang=payload.lang,
      rating_1_5=None,
      time_on_screen_ms=None,
      route_used=route_used,
      confidence=confidence,
      sources_count=sources_count,
      error_code=error_code,
      latency_ms=latency_ms,
      hashed_query=hash_query(query),
    )
  except Exception:
    pass

