import json
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.services.hash_service import hash_query


def get_offline_pack_path() -> str:
  env_val = os.getenv("OFFLINE_PACK_PATH")
  if env_val:
    return env_val
  # Try common locations: repo root (local dev) then app root (container)
  here = Path(__file__).resolve().parent
  candidates = [
    here.parents[3] / "data" / "offline_pack" / "offline_pack.json",  # local: repo root
    here.parents[1] / "data" / "offline_pack" / "offline_pack.json",  # container: /app/
    Path.cwd() / "data" / "offline_pack" / "offline_pack.json",
  ]
  for p in candidates:
    try:
      if p.exists():
        return str(p)
    except Exception:
      continue
  return str(candidates[0])


def normalize(text: str) -> str:
  text = text.strip().lower()
  # remove diacritics
  text = "".join(
    c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
  )
  text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text, flags=re.UNICODE)
  text = re.sub(r"\s+", " ", text).strip()
  return text


def score(query: str, variant: str) -> float:
  if not query or not variant:
    return 0.0
  if query == variant:
    return 1.0
  if query in variant or variant in query:
    return 0.9
  q_tokens = set(query.split())
  v_tokens = set(variant.split())
  if not q_tokens or not v_tokens:
    return 0.0
  intersection = q_tokens.intersection(v_tokens)
  union = q_tokens.union(v_tokens)
  return len(intersection) / len(union)


@lru_cache(maxsize=1)
def load_offline_pack() -> List[Dict]:
  path = Path(get_offline_pack_path())
  if not path.exists():
    return []
  data = json.loads(path.read_text(encoding="utf-8"))
  return data if isinstance(data, list) else []


def match_offline(query: str, lang: str) -> Tuple[Optional[Dict], float]:
  items = [i for i in load_offline_pack() if i.get("lang") == lang]
  if not items:
    return None, 0.0
  nq = normalize(query)
  best = None
  best_score = 0.0
  for item in items:
    variants = item.get("question_variants", [])
    for v in variants:
      sv = normalize(v)
      s = score(nq, sv)
      if s > best_score:
        best_score = s
        best = item
  return best, best_score


def get_suggestions(query: str, lang: str, limit: int = 3) -> List[str]:
  items = [i for i in load_offline_pack() if i.get("lang") == lang]
  if not items:
    return []
  nq = normalize(query)
  candidates: List[Tuple[str, float]] = []
  for item in items:
    tags = [normalize(t) for t in item.get("tags", []) if isinstance(t, str)]
    tag_hit = any(t and t in nq for t in tags)
    for v in item.get("question_variants", []):
      sv = normalize(v)
      s = score(nq, sv)
      if tag_hit:
        s += 0.15
      candidates.append((v, s))
  candidates.sort(key=lambda x: x[1], reverse=True)
  seen = set()
  results = []
  for text, s in candidates:
    if text in seen:
      continue
    if s <= 0:
      continue
    seen.add(text)
    results.append(text)
    if len(results) >= limit:
      break
  return results
