#!/usr/bin/env python3
"""Send generated summary via Resend email."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import resend


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="summary.txt")
    parser.add_argument("--subject", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = Path(args.input).read_text(encoding="utf-8").strip()
    if not summary:
        raise RuntimeError("Summary is empty; nothing to send.")

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    recipient = os.getenv("STANDUP_EMAIL", "").strip()
    from_email = os.getenv("RESEND_FROM", "Breaking Standup <onboarding@resend.dev>").strip()
    subject = args.subject.strip() or os.getenv("STANDUP_EMAIL_SUBJECT", "Standup Update").strip()

    if not api_key:
        raise RuntimeError("RESEND_API_KEY is required")
    if not recipient:
        raise RuntimeError("STANDUP_EMAIL is required")

    resend.api_key = api_key
    resend.Emails.send(
        {
            "from": from_email,
            "to": [recipient],
            "subject": subject,
            "text": summary,
        }
    )
    print("Standup email sent.")


if __name__ == "__main__":
    main()
