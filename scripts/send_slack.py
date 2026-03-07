#!/usr/bin/env python3
"""Send generated summary to Slack DM."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from slack_sdk import WebClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="summary.txt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = Path(args.input).read_text(encoding="utf-8").strip()
    if not summary:
        raise RuntimeError("Summary is empty; nothing to send.")

    token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    user_id = os.getenv("SLACK_USER_ID", "").strip()
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is required")
    if not user_id:
        raise RuntimeError("SLACK_USER_ID is required")

    client = WebClient(token=token)
    dm_channel = client.conversations_open(users=[user_id])["channel"]["id"]
    client.chat_postMessage(channel=dm_channel, text=summary)
    print("Slack DM sent.")


if __name__ == "__main__":
    main()
