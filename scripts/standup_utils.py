"""Helpers for building ticket-focused standup payloads."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


PREFIX_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)*(?:feat|fix|chore|docs|style|refactor|test|perf|ci|build|wip|bugfix)\s*[:\-]\s*",
    re.IGNORECASE,
)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_text(text: str) -> str:
    normalized = NON_ALNUM_RE.sub(" ", (text or "").lower())
    return " ".join(normalized.split())


def _strip_common_prefixes(message: str) -> str:
    cleaned = message or ""
    while True:
        updated = PREFIX_RE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned.strip()


def _title_phrases(title: str, phrase_len: int = 4) -> Iterable[str]:
    tokens = _normalize_text(title).split()
    if len(tokens) < phrase_len:
        return []
    return [" ".join(tokens[i : i + phrase_len]) for i in range(0, len(tokens) - phrase_len + 1)]


def _commit_matches_card(card: Dict[str, Any], commit: Dict[str, Any]) -> bool:
    raw_message = str(commit.get("message") or "")
    normalized_message = _normalize_text(_strip_common_prefixes(raw_message))

    card_id = str(card.get("id") or "").strip()
    if card_id and card_id in raw_message:
        return True

    title = str(card.get("title") or "").strip()
    normalized_title = _normalize_text(title)
    if normalized_title and normalized_title in normalized_message:
        return True

    for phrase in _title_phrases(title):
        if phrase and phrase in normalized_message:
            return True

    return False


def _proof_commits_for_card(card: Dict[str, Any], commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    proof: List[Dict[str, Any]] = []
    for commit in commits:
        if _commit_matches_card(card, commit):
            proof.append(
                {
                    "repo": commit.get("repo"),
                    "sha": commit.get("sha"),
                    "message": commit.get("message"),
                    "html_url": commit.get("html_url"),
                }
            )
    return proof


def enrich_cards_with_commit_proof(cards: List[Dict[str, Any]], commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach matching commits to each card using ID/title-based matching."""
    enriched: List[Dict[str, Any]] = []
    for card in cards:
        item = {
            "id": card.get("id"),
            "title": card.get("title"),
            "card_status": card.get("cardStatus"),
            "moved_on": card.get("movedOn"),
            "updated_on": card.get("updatedOn"),
            "matching_commits": _proof_commits_for_card(card, commits),
        }
        enriched.append(item)
    return enriched


def dedupe_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupe by card ID, falling back to title when needed."""
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for card in cards:
        card_id = str(card.get("id") or "").strip()
        title = str(card.get("title") or "").strip().lower()
        key = f"id:{card_id}" if card_id else f"title:{title}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)

    return deduped
