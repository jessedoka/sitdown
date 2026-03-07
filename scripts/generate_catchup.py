#!/usr/bin/env python3
"""Generate a weekly catch-up summary with OpenAI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI


SYSTEM_PROMPT = """You are writing a weekly spoken catch-up update for a team meeting.

Requirements:
- Focus on what was achieved over the last week at a high level.
- Mention meaningful themes and outcomes, not implementation minutiae.
- Keep it concise and natural to read aloud.
- Output a short paragraph or two, not a long bullet list.
"""


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

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=700,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Summarise this weekly activity data as a spoken team catch-up update.\n\n"
                    f"{json.dumps(data, ensure_ascii=True)}"
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
