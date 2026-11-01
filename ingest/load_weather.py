import os
import sys

import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.helper import DB_DSN, SEASON, fetch_openf1, find_openf1_session_for_race, get_schedule, parse_iso_datetime


def insert_weather(cur, session_key, weather_rows):
    if not weather_rows:
        return

    rows = []
    for row in weather_rows:
        rows.append(
            (
                parse_iso_datetime(row.get("date")),
                str(session_key),
                row.get("air_temperature"),
                row.get("track_temperature"),
                row.get("humidity"),
                row.get("pressure"),
                bool(row.get("rainfall")),
                row.get("wind_speed"),
                row.get("wind_direction"),
            )
        )

    if rows:
        cur.executemany(
            """
            INSERT INTO weather (
                time,
                session_key,
                air_temp,
                track_temp,
                humidity,
                pressure,
                rainfall,
                wind_speed,
                wind_direction
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, session_key)
            DO NOTHING
            """,
            rows,
        )


def main():
    schedule = get_schedule(SEASON)
    openf1_sessions = fetch_openf1("sessions", year=SEASON)

    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            for race in schedule:
                meta = find_openf1_session_for_race(race, openf1_sessions)
                if meta is None:
                    continue

                session_key = meta["session_key"]
                weather_rows = fetch_openf1("weather", session_key=session_key)
                insert_weather(cur, session_key, weather_rows)
                print("inserted weather for", session_key)

            conn.commit()


if __name__ == "__main__":
    main()
