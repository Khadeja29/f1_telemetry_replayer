import argparse
import os
import sys

import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.helper import DB_DSN, SEASON, fetch_openf1, find_openf1_session_for_race, get_schedule, parse_iso_datetime


def insert_telemetry(cur, session_key, telemetry_rows):
    if not telemetry_rows:
        return

    driver_map = {}
    try:
        drivers = fetch_openf1("drivers", session_key=session_key)
        for driver in drivers:
            number = driver.get("driver_number")
            if number is not None:
                driver_map[int(number)] = driver.get("full_name") or driver.get("broadcast_name") or str(number)
    except Exception:
        driver_map = {}

    rows = []
    for row in telemetry_rows:
        driver_number = row.get("driver_number")
        driver_name = driver_map.get(int(driver_number), f"driver_{driver_number}") if driver_number is not None else "unknown"
        rows.append(
            (
                parse_iso_datetime(row.get("date")),
                None,
                None,
                str(session_key),
                driver_name,
                int(driver_number) if driver_number is not None else None,
                row.get("speed"),
                row.get("rpm"),
                row.get("n_gear"),
                row.get("throttle"),
                bool(row.get("brake", 0) != 0),
                row.get("drs"),
                "openf1",
            )
        )

    if rows:
        cur.executemany(
            """
            INSERT INTO car_telemetry (
                time,
                session_time,
                slice_time,
                session,
                driver,
                driver_number,
                speed,
                rpm,
                gear,
                throttle,
                brake,
                drs,
                source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, session, driver_number)
            DO NOTHING
            """,
            rows,
        )


def main():
    parser = argparse.ArgumentParser(description="Load F1 telemetry from OpenF1 into TimescaleDB.")
    parser.add_argument("--year", type=int, default=SEASON, help="Season to load (default: current SEASON).")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N races for testing.")
    parser.add_argument("--session-key", type=int, default=None, help="Process only one session key for a focused test run.")
    args = parser.parse_args()

    schedule = get_schedule(args.year)
    openf1_sessions = fetch_openf1("sessions", year=args.year)
    processed_races = 0

    print(f"Starting telemetry load for season {args.year}. Found {len(schedule)} race entries.", flush=True)

    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            for race in schedule:
                meta = find_openf1_session_for_race(race, openf1_sessions)
                if meta is None:
                    continue

                session_key = meta["session_key"]
                if args.session_key is not None and session_key != args.session_key:
                    continue

                processed_races += 1
                print(f"Processing race: {race.get('raceName')} (session_key={session_key})", flush=True)

                drivers = fetch_openf1("drivers", session_key=session_key)
                for driver in drivers:
                    driver_number = driver.get("driver_number")
                    if driver_number is None:
                        continue

                    telemetry_rows = fetch_openf1("car_data", session_key=session_key, driver_number=int(driver_number))
                    row_count = len(telemetry_rows) if isinstance(telemetry_rows, list) else 0
                    print(f"  driver {driver_number}: fetched {row_count} telemetry rows", flush=True)
                    insert_telemetry(cur, session_key, telemetry_rows)

                if args.limit is not None and processed_races >= args.limit:
                    break

            conn.commit()

    print(f"Completed telemetry load for {processed_races} race(s).", flush=True)


if __name__ == "__main__":
    main()
