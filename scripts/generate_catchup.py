#!/usr/bin/env python3
"""Generate a weekly catch-up summary with OpenAI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI
from standup_utils import dedupe_cards, enrich_cards_with_commit_proof


SYSTEM_PROMPT = """You are writing a weekly catch-up as a structured markdown ticket list.

Return exactly these sections in this order:
1) ## Tickets completed this week (with proof)
2) ## Tickets in progress

Formatting requirements:
- Use bullet points for tickets.
- Each ticket bullet must include the ticket title and ID.
- Under each ticket, add either:
  - "Proof:" followed by matching commit message(s) and short repo/SHA details, OR
  - "(No matching commits found)" when there is no proof commit.
- Keep the output concise and readout-friendly.
- Do not invent tickets or commits.
"""


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

    return {
        "mode": data.get("mode"),
        "generated_at": data.get("generated_at"),
        "windows": data.get("windows"),
        "tickets_completed": enrich_cards_with_commit_proof(completed_this_week, commits),
        "tickets_in_progress": enrich_cards_with_commit_proof(in_progress, commits),
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
                    "Format this weekly ticket activity as the required structured catch-up list.\n\n"
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
