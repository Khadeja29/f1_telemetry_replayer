import datetime
import json
import os
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError

import pandas as pd

SEASON = 2024
DB_DSN = (
    f"dbname={os.environ.get('PGDATABASE', 'telemetry')} "
    f"user={os.environ.get('PGUSER', 'f1')} "
    f"password={os.environ.get('PGPASSWORD', 'f1password')} "
    f"host={os.environ.get('PGHOST', '127.0.0.1')} "
    f"port={os.environ.get('PGPORT', '5432')}"
)
OPENF1_BASE_URL = "https://api.openf1.org/v1"


def parse_iso_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(cleaned)
    return None


def to_interval(value):
    if value is None:
        return None
    if isinstance(value, datetime.timedelta):
        return value
    return datetime.timedelta(seconds=float(value))


def fetch_openf1(endpoint: str, **params):
    query = urllib.parse.urlencode({str(k): v for k, v in params.items() if v is not None})
    url = f"{OPENF1_BASE_URL}/{endpoint.lstrip('/')}"
    if query:
        url = f"{url}?{query}"

    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "f1-telemetry-replayer"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            time.sleep(1.5)
            return payload
        except HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def get_schedule(season: int = SEASON):
    meetings = fetch_openf1("meetings", year=season)
    sessions = fetch_openf1("sessions", year=season)
    meetings_by_key = {int(meeting.get("meeting_key")): meeting for meeting in meetings if meeting.get("meeting_key") is not None}

    schedule = []
    for session in sessions:
        if session.get("session_name") != "Race":
            continue

        meeting_key = session.get("meeting_key")
        meeting = meetings_by_key.get(int(meeting_key), {}) if meeting_key is not None else {}
        race_date = parse_iso_datetime(session.get("date_start"))
        schedule.append(
            {
                "meeting_key": meeting_key,
                "round": len(schedule) + 1,
                "raceName": meeting.get("meeting_name") or meeting.get("meeting_official_name") or session.get("session_name") or "Race",
                "country": meeting.get("country_name") or session.get("country_name"),
                "circuitName": meeting.get("circuit_short_name") or meeting.get("location") or session.get("circuit_short_name"),
                "raceDate": race_date.date() if race_date else None,
                "date_start": session.get("date_start"),
            }
        )

    return schedule


def build_session_key(season: int, round_num: int, race_name: str) -> str:
    return f"{season}_{round_num:02d}_{race_name.replace(' ', '_')}"


def build_start_time(race) -> datetime.datetime:
    value = race.get("date_start") or race.get("raceDate")
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        return parse_iso_datetime(value)
    if value is not None:
        return datetime.datetime.combine(value, datetime.time.min)
    return datetime.datetime.now(datetime.timezone.utc)


def find_openf1_session_for_race(race, openf1_sessions):
    target_meeting = race.get("meeting_key")
    if target_meeting is not None:
        for session in openf1_sessions:
            if session.get("session_name") == "Race" and session.get("meeting_key") == target_meeting:
                return session

    target_date = race.get("raceDate")
    if target_date is not None:
        for session in openf1_sessions:
            if session.get("session_name") != "Race":
                continue
            date_start = session.get("date_start")
            if not date_start:
                continue
            try:
                session_date = datetime.datetime.fromisoformat(date_start.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            if session_date == target_date:
                return session
    return None


def first_present(mapping, *keys):
    for key in keys:
        if key in mapping:
            value = mapping[key]
            if value is not None and not pd.isna(value):
                return value
    return None
