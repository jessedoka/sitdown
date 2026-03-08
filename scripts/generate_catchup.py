#!/usr/bin/env python3
"""Generate a weekly catch-up summary with OpenAI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI
from standup_utils import commits_without_ticket, dedupe_cards, enrich_cards_with_commit_proof


SYSTEM_PROMPT = """You are writing a concise morning email to yourself as a weekly catch-up.

Return exactly these sections in this order:
1) Tickets completed this week (with proof)
2) Tickets in progress
3) Other work

Formatting requirements:
- Use bullet points for tickets.
- Each ticket bullet must include the ticket title and ID.
- Under each ticket, add either:
  - "Proof:" followed by matching commit message(s), repo names, and short repo/SHA details, OR
  - "(No matching commits found)" when there is no proof commit.
- Mention compact changed-files detail when available for proof commits.
- In Other work, list unmatched commits as short bullets with repo + SHA + message.
- Keep the output concise and readout-friendly.
- Do not invent tickets or commits.
"""


def build_card_status_counts(cards: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for card in cards:
        status = str(card.get("cardStatus") or "unknown").strip().lower() or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def build_weekly_payload(data: dict) -> dict:
    leankit = data.get("leankit") or {}
    github = data.get("github") or {}

    commits = github.get("commits") or []
    cards_in_main_window = leankit.get("cards_in_main_window") or []
    started_cards = leankit.get("started_cards") or []

    completed_this_week = [
        card for card in cards_in_main_window if "finished" in str(card.get("cardStatus") or "").lower()
    ]
    in_progress = dedupe_cards(started_cards + cards_in_main_window)
    in_progress = [
        card for card in in_progress if "started" in str(card.get("cardStatus") or "").lower()
    ]
    relevant_cards = dedupe_cards(completed_this_week + in_progress)

    return {
        "mode": data.get("mode"),
        "generated_at": data.get("generated_at"),
        "windows": data.get("windows"),
        "cards_by_status": build_card_status_counts(leankit.get("cards") or []),
        "tickets_completed": enrich_cards_with_commit_proof(completed_this_week, commits),
        "tickets_in_progress": enrich_cards_with_commit_proof(in_progress, commits),
        "other_work": commits_without_ticket(relevant_cards, commits),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data.json")
    parser.add_argument("--output", default="summary.txt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if data.get("annual_leave"):
        output_path.write_text("Annual leave detected. No weekly catch-up generated.", encoding="utf-8")
        print("Annual leave detected; skipped generation.")
        return

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    payload = build_weekly_payload(data)

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=700,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Format this as a concise morning catch-up email to myself using the required sections.\n\n"
                    f"{json.dumps(payload, ensure_ascii=True)}"
                ),
            }
        ],
    )

    summary = (response.choices[0].message.content or "").strip()
    if not summary:
        raise RuntimeError("OpenAI returned an empty summary.")
    output_path.write_text(summary + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")

if __name__ == "__main__":
    main()
