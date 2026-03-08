"""Helpers for building ticket-focused standup payloads."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


PREFIX_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)*(?:feat|fix|chore|docs|style|refactor|test|perf|ci|build|wip|bugfix)\s*[:\-]\s*",
    re.IGNORECASE,
)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
TICKET_TOKEN_RE = re.compile(r"\b([sd])(?:#|-)\s*(\d+)\b", re.IGNORECASE)


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


def _extract_ticket_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for prefix, number in TICKET_TOKEN_RE.findall(text or ""):
        tokens.add(f"{prefix.upper()}-{number}")
    return tokens


def _commit_matches_card(card: Dict[str, Any], commit: Dict[str, Any]) -> bool:
    raw_message = str(commit.get("message") or "")
    normalized_message = _normalize_text(_strip_common_prefixes(raw_message))
    commit_tokens = _extract_ticket_tokens(raw_message)
    card_tokens = _extract_ticket_tokens(str(card.get("title") or ""))
    if card_tokens and (card_tokens & commit_tokens):
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
            files = commit.get("files") if isinstance(commit.get("files"), list) else []
            proof.append(
                {
                    "repo": commit.get("repo"),
                    "sha": commit.get("sha"),
                    "message": commit.get("message"),
                    "date": commit.get("date"),
                    "stats": commit.get("stats") if isinstance(commit.get("stats"), dict) else {},
                    "files": [
                        {
                            "filename": f.get("filename"),
                            "status": f.get("status"),
                            "changes": f.get("changes"),
                            "additions": f.get("additions"),
                            "deletions": f.get("deletions"),
                        }
                        for f in files
                        if isinstance(f, dict)
                    ],
                    "html_url": commit.get("html_url"),
                }
            )
    return proof


def enrich_cards_with_commit_proof(cards: List[Dict[str, Any]], commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach matching commits to each card using ID/title-based matching."""
    enriched: List[Dict[str, Any]] = []
    for card in cards:
        matching_commits = _proof_commits_for_card(card, commits)
        item = {
            "id": card.get("id"),
            "title": card.get("title"),
            "board_title": card.get("boardTitle"),
            "lane_title": card.get("laneTitle"),
            "url": card.get("url"),
            "card_status": card.get("cardStatus"),
            "moved_on": card.get("movedOn"),
            "updated_on": card.get("updatedOn"),
            "matching_commits": matching_commits,
            "proof_commit_count": len(matching_commits),
            "proof_repos": sorted(
                {
                    str(commit.get("repo"))
                    for commit in matching_commits
                    if str(commit.get("repo") or "").strip()
                }
            ),
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


def commits_without_ticket(cards: List[Dict[str, Any]], commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return commits that do not match any provided card."""
    unmatched: List[Dict[str, Any]] = []
    for commit in commits:
        if any(_commit_matches_card(card, commit) for card in cards):
            continue
        files = commit.get("files") if isinstance(commit.get("files"), list) else []
        unmatched.append(
            {
                "repo": commit.get("repo"),
                "sha": commit.get("sha"),
                "message": commit.get("message"),
                "date": commit.get("date"),
                "stats": commit.get("stats") if isinstance(commit.get("stats"), dict) else {},
                "files": [
                    {
                        "filename": f.get("filename"),
                        "status": f.get("status"),
                        "changes": f.get("changes"),
                        "additions": f.get("additions"),
                        "deletions": f.get("deletions"),
                    }
                    for f in files
                    if isinstance(f, dict)
                ],
                "html_url": commit.get("html_url"),
            }
        )
    return unmatched
