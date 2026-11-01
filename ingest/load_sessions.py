import os
import sys

import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.helper import DB_DSN, SEASON, fetch_openf1, find_openf1_session_for_race, get_schedule, parse_iso_datetime


def insert_session(cur, session_key, race, round_num, start_time):
    cur.execute(
        """
        INSERT INTO sessions (
            session_key,
            year,
            round,
            event_name,
            country,
            circuit,
            session_type,
            start_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (session_key) DO UPDATE SET
            year = EXCLUDED.year,
            round = EXCLUDED.round,
            event_name = EXCLUDED.event_name,
            country = EXCLUDED.country,
            circuit = EXCLUDED.circuit,
            session_type = EXCLUDED.session_type,
            start_time = EXCLUDED.start_time
        """,
        (
            str(session_key),
            SEASON,
            round_num,
            race["raceName"],
            race["country"],
            race["circuitName"],
            "R",
            start_time,
        ),
    )


def main():
    schedule = get_schedule(SEASON)
    openf1_sessions = fetch_openf1("sessions", year=SEASON)

    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            for race in schedule:
                round_num = int(race["round"])
                meta = find_openf1_session_for_race(race, openf1_sessions)
                if meta is None:
                    continue

                session_key = meta["session_key"]
                start_time = parse_iso_datetime(meta["date_start"])

                insert_session(cur, session_key, race, round_num, start_time)
                print("inserted session", session_key, race["raceName"], start_time)

            conn.commit()


if __name__ == "__main__":
    main()
