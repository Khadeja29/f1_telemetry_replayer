import os
import sys

import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.helper import DB_DSN, SEASON, fetch_openf1, find_openf1_session_for_race, get_schedule, parse_iso_datetime, to_interval


def insert_laps(cur, session_key, lap_rows):
    if not lap_rows:
        return

    driver_meta = {}
    try:
        drivers = fetch_openf1("drivers", session_key=session_key)
        for driver in drivers:
            number = driver.get("driver_number")
            if number is not None:
                driver_meta[int(number)] = driver.get("full_name") or driver.get("broadcast_name") or str(number)
    except Exception:
        driver_meta = {}

    rows = []
    for lap in lap_rows:
        driver_number = lap.get("driver_number")
        if driver_number is None:
            continue

        driver_name = driver_meta.get(int(driver_number), f"driver_{driver_number}")
        rows.append(
            (
                str(session_key),
                driver_name,
                int(driver_number),
                None,
                lap.get("lap_number"),
                parse_iso_datetime(lap.get("date_start")),
                to_interval(lap.get("lap_duration")),
                to_interval(lap.get("duration_sector_1")),
                to_interval(lap.get("duration_sector_2")),
                to_interval(lap.get("duration_sector_3")),
                lap.get("i1_speed"),
                lap.get("i2_speed"),
                None,
                lap.get("st_speed"),
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )

    if rows:
        cur.executemany(
            """
            INSERT INTO laps (
                session_key,
                driver,
                driver_number,
                team,
                lap_number,
                lap_start,
                lap_time,
                sector1_time,
                sector2_time,
                sector3_time,
                speed_i1,
                speed_i2,
                speed_fl,
                speed_st,
                compound,
                tyre_life,
                fresh_tyre,
                stint,
                pit_in,
                pit_out,
                position,
                track_status,
                is_accurate,
                deleted
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_key, driver, lap_number) DO UPDATE SET
                driver_number = EXCLUDED.driver_number,
                team = EXCLUDED.team,
                lap_start = EXCLUDED.lap_start,
                lap_time = EXCLUDED.lap_time,
                sector1_time = EXCLUDED.sector1_time,
                sector2_time = EXCLUDED.sector2_time,
                sector3_time = EXCLUDED.sector3_time,
                speed_i1 = EXCLUDED.speed_i1,
                speed_i2 = EXCLUDED.speed_i2,
                speed_fl = EXCLUDED.speed_fl,
                speed_st = EXCLUDED.speed_st,
                compound = EXCLUDED.compound,
                tyre_life = EXCLUDED.tyre_life,
                fresh_tyre = EXCLUDED.fresh_tyre,
                stint = EXCLUDED.stint,
                pit_in = EXCLUDED.pit_in,
                pit_out = EXCLUDED.pit_out,
                position = EXCLUDED.position,
                track_status = EXCLUDED.track_status,
                is_accurate = EXCLUDED.is_accurate,
                deleted = EXCLUDED.deleted
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
                lap_rows = fetch_openf1("laps", session_key=session_key)
                insert_laps(cur, session_key, lap_rows)
                print("inserted laps for", session_key)

            conn.commit()


if __name__ == "__main__":
    main()
