#!/usr/bin/env python3
"""Collect standup/catch-up inputs from GitHub, LeanKit, and Google Calendar."""

from __future__ import annotations

import argparse
import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build


GITHUB_API = "https://api.github.com"
LEANKIT_URL = (
    "https://singletrack.leankit.com/io/user/me/card"
    "?type=assigned&cardStatus=started,finished"
)
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


@dataclass
class Window:
    label: str
    start: datetime
    end: datetime

    @property
    def since_iso(self) -> str:
        return self.start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @property
    def start_iso(self) -> str:
        return self.start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @property
    def end_iso(self) -> str:
        return self.end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["daily", "weekly"], required=True)
    parser.add_argument("--output", default="data.json")
    parser.add_argument("--timezone", default="Europe/London")
    parser.add_argument("--github-org", default=os.getenv("GITHUB_ORG", "singletracksystems"))
    parser.add_argument("--github-author", default=os.getenv("GITHUB_AUTHOR", "jessedoka"))
    parser.add_argument("--calendar-id", default=os.getenv("GOOGLE_CALENDAR_ID", "primary"))
    return parser.parse_args()


def now_in_tz(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def get_windows(mode: str, tz_name: str) -> Dict[str, Window]:
    now = now_in_tz(tz_name)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if mode == "daily":
        yesterday_start = today_start - timedelta(days=1)
        return {
            "main": Window("daily", yesterday_start, now),
            "yesterday": Window("yesterday", yesterday_start, today_start),
            "today": Window("today", today_start, today_start + timedelta(days=1)),
        }

    # Weekly: from last Tuesday start-of-day until now. If today is Tuesday, go back 7 days.
    weekday = today_start.weekday()  # Monday=0, Tuesday=1
    days_since_tuesday = (weekday - 1) % 7
    if days_since_tuesday == 0:
        days_since_tuesday = 7
    weekly_start = today_start - timedelta(days=days_since_tuesday)
    return {
        "main": Window("weekly", weekly_start, now),
        "today": Window("today", today_start, today_start + timedelta(days=1)),
    }


def github_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def paged_get(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Iterable[Any]:
    page = 1
    while True:
        merged = {"per_page": 100, "page": page}
        if params:
            merged.update(params)
        response = requests.get(url, headers=headers, params=merged, timeout=30)
        response.raise_for_status()
        items = response.json()
        if not isinstance(items, list):
            break
        if not items:
            break
        for item in items:
            yield item
        if len(items) < 100:
            break
        page += 1


def collect_github_data(org: str, author: str, since_iso: str, token: str) -> Dict[str, Any]:
    headers = github_headers(token)
    repos = list(paged_get(f"{GITHUB_API}/orgs/{org}/repos", headers))
    commits_out: List[Dict[str, Any]] = []

    for repo in repos:
        full_name = repo.get("full_name")
        if not full_name:
            continue

        commits = list(
            paged_get(
                f"{GITHUB_API}/repos/{full_name}/commits",
                headers,
                {"author": author, "since": since_iso},
            )
        )

        for commit in commits:
            sha = commit.get("sha")
            if not sha:
                continue
            detail = requests.get(
                f"{GITHUB_API}/repos/{full_name}/commits/{sha}",
                headers=headers,
                timeout=30,
            )
            detail.raise_for_status()
            detail_json = detail.json()
            files = detail_json.get("files", [])
            commits_out.append(
                {
                    "repo": full_name,
                    "sha": sha,
                    "html_url": commit.get("html_url"),
                    "message": (commit.get("commit") or {}).get("message", ""),
                    "author_name": ((commit.get("commit") or {}).get("author") or {}).get("name"),
                    "date": ((commit.get("commit") or {}).get("author") or {}).get("date"),
                    "stats": detail_json.get("stats", {}),
                    "files": [
                        {
                            "filename": f.get("filename"),
                            "status": f.get("status"),
                            "additions": f.get("additions"),
                            "deletions": f.get("deletions"),
                            "changes": f.get("changes"),
                        }
                        for f in files
                    ],
                }
            )

    return {
        "org": org,
        "author": author,
        "since": since_iso,
        "repos_scanned": len(repos),
        "commit_count": len(commits_out),
        "commits": commits_out,
    }


def parse_iso_maybe(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def card_status(card: Dict[str, Any]) -> str:
    for key in ("cardStatus", "status", "laneClassType", "laneType"):
        val = card.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    return ""


def normalize_card(card: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": card.get("id"),
        "title": card.get("title"),
        "boardTitle": card.get("boardTitle"),
        "laneTitle": card.get("laneTitle"),
        "movedOn": card.get("movedOn"),
        "updatedOn": card.get("updatedOn"),
        "assignedUsers": card.get("assignedUsers"),
        "url": card.get("url"),
        "cardStatus": card.get("cardStatus") or card.get("status"),
    }


def collect_leankit_data(token: str, windows: Dict[str, Window], mode: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(LEANKIT_URL, headers=headers, timeout=30)
    response.raise_for_status()
    body = response.json()
    cards = body.get("cards", body if isinstance(body, list) else [])
    if not isinstance(cards, list):
        cards = []

    normalized = [normalize_card(c) for c in cards if isinstance(c, dict)]
    main_start = windows["main"].start
    in_main = []
    started_now = []
    for card in normalized:
        moved = parse_iso_maybe(card.get("movedOn"))
        status = card_status(card)
        if moved and moved >= main_start:
            in_main.append(card)
        if "started" in status:
            started_now.append(card)

    result: Dict[str, Any] = {
        "count": len(normalized),
        "cards": normalized,
        "cards_in_main_window": in_main,
        "started_cards": started_now,
    }

    if mode == "daily":
        yesterday = windows["yesterday"]
        finished_yesterday = []
        for card in normalized:
            moved = parse_iso_maybe(card.get("movedOn"))
            status = card_status(card)
            if moved and yesterday.start <= moved < yesterday.end and "finished" in status:
                finished_yesterday.append(card)
        result["finished_yesterday"] = finished_yesterday

    return result


def load_calendar_service() -> Any:
    encoded = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "").strip()
    if not encoded:
        raise RuntimeError("GOOGLE_CALENDAR_CREDENTIALS secret is missing")

    decoded = base64.b64decode(encoded).decode("utf-8")
    info = json.loads(decoded)
    creds = service_account.Credentials.from_service_account_info(info, scopes=[CALENDAR_SCOPE])
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def collect_calendar_data(calendar_id: str, windows: Dict[str, Window], mode: str) -> Dict[str, Any]:
    service = load_calendar_service()

    main_window = windows["today"] if mode == "daily" else windows["main"]
    req = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=main_window.start_iso,
            timeMax=main_window.end_iso,
            singleEvents=True,
            orderBy="startTime",
        )
    )
    events = req.execute().get("items", [])
    compact_events = [
        {
            "id": e.get("id"),
            "summary": e.get("summary", ""),
            "start": (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date"),
            "end": (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date"),
            "htmlLink": e.get("htmlLink"),
        }
        for e in events
    ]

    leave_detected = any("annual leave" in (evt.get("summary") or "").lower() for evt in compact_events)

    return {
        "calendar_id": calendar_id,
        "window_start": main_window.start_iso,
        "window_end": main_window.end_iso,
        "event_count": len(compact_events),
        "events": compact_events,
        "annual_leave": leave_detected,
    }


def write_github_output(annual_leave: bool) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as fh:
        fh.write(f"annual_leave={'true' if annual_leave else 'false'}\n")


def main() -> None:
    args = parse_args()
    windows = get_windows(args.mode, args.timezone)

    github_token = os.getenv("GITHUB_TOKEN", "").strip()
    if not github_token:
        raise RuntimeError("GITHUB_TOKEN is required")

    leankit_token = os.getenv("LEANKIT_BEARER_TOKEN", "").strip()
    if not leankit_token:
        raise RuntimeError("LEANKIT_BEARER_TOKEN is required")

    github_data = collect_github_data(
        org=args.github_org,
        author=args.github_author,
        since_iso=windows["main"].since_iso,
        token=github_token,
    )
    leankit_data = collect_leankit_data(leankit_token, windows, args.mode)
    calendar_data = collect_calendar_data(args.calendar_id, windows, args.mode)

    annual_leave = bool(calendar_data.get("annual_leave"))
    write_github_output(annual_leave)

    payload = {
        "mode": args.mode,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": args.timezone,
        "windows": {
            key: {"label": w.label, "start": w.start_iso, "end": w.end_iso}
            for key, w in windows.items()
        },
        "annual_leave": annual_leave,
        "github": github_data,
        "leankit": leankit_data,
        "calendar": calendar_data,
    }

    out_path = Path(args.output)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} (annual_leave={annual_leave})")


if __name__ == "__main__":
    main()
