import argparse
import os
import sys

import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.helper import DB_DSN


def print_query_result(label, rows):
    if not rows:
        print(f"\n{label}: no data found")
        return

    headers = list(rows[0].keys())
    widths = [len(str(header)) for header in headers]

    for row in rows:
        values = [str(value) for value in row.values()]
        for i, value in enumerate(values):
            widths[i] = max(widths[i], len(value))

    def format_row(values):
        return " | ".join(str(value).ljust(widths[i]) for i, value in enumerate(values))

    print(f"\n{label}")
    print(format_row(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(format_row([row[h] for h in headers]))


def get_session_filter(session_key=None):
    return "WHERE session = %s" if session_key is not None else ""


def main():
    parser = argparse.ArgumentParser(description="Generate quick F1 insights from the loaded database.")
    parser.add_argument("--session-key", type=str, default=None, help="Optional session key to focus the analysis on one race.")
    args = parser.parse_args()

    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            print("F1 telemetry insights")
            print("=" * 60)

            cur.execute("SELECT COUNT(*) AS session_rows FROM sessions")
            session_rows = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) AS lap_rows FROM laps")
            lap_rows = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) AS weather_rows FROM weather")
            weather_rows = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) AS telemetry_rows FROM car_telemetry")
            telemetry_rows = cur.fetchone()[0]

            print(f"sessions: {session_rows}")
            print(f"laps: {lap_rows}")
            print(f"weather: {weather_rows}")
            print(f"telemetry: {telemetry_rows}")

            if args.session_key is not None:
                cur.execute(
                    """
                    SELECT session, driver_number,
                           ROUND(AVG(speed)::numeric, 2) AS avg_speed,
                           MAX(speed) AS max_speed
                    FROM car_telemetry
                    WHERE session = %s
                    GROUP BY session, driver_number
                    ORDER BY avg_speed DESC, max_speed DESC
                    LIMIT 10
                    """,
                    (args.session_key,),
                )
                print_query_result("Top average speeds by driver", [
                    {"session": row[0], "driver_number": row[1], "avg_speed": row[2], "max_speed": row[3]}
                    for row in cur.fetchall()
                ])

                cur.execute(
                    """
                    SELECT session, driver_number,
                           ROUND(AVG(rpm)::numeric, 2) AS avg_rpm,
                           MAX(rpm) AS max_rpm
                    FROM car_telemetry
                    WHERE session = %s
                    GROUP BY session, driver_number
                    ORDER BY avg_rpm DESC
                    LIMIT 10
                    """,
                    (args.session_key,),
                )
                print_query_result("Top average RPM by driver", [
                    {"session": row[0], "driver_number": row[1], "avg_rpm": row[2], "max_rpm": row[3]}
                    for row in cur.fetchall()
                ])

                cur.execute(
                    """
                    SELECT w.session_key,
                           ROUND(AVG(w.air_temp)::numeric, 2) AS avg_air_temp,
                           ROUND(AVG(w.track_temp)::numeric, 2) AS avg_track_temp,
                           ROUND(AVG(w.wind_speed)::numeric, 2) AS avg_wind_speed
                    FROM weather w
                    WHERE w.session_key = %s
                    GROUP BY w.session_key
                    """,
                    (args.session_key,),
                )
                print_query_result("Weather summary", [
                    {"session_key": row[0], "avg_air_temp": row[1], "avg_track_temp": row[2], "avg_wind_speed": row[3]}
                    for row in cur.fetchall()
                ])
            else:
                cur.execute(
                    """
                    SELECT c.session, c.driver_number,
                           ROUND(AVG(c.speed)::numeric, 2) AS avg_speed,
                           MAX(c.speed) AS max_speed
                    FROM car_telemetry c
                    GROUP BY c.session, c.driver_number
                    ORDER BY avg_speed DESC, max_speed DESC
                    LIMIT 10
                    """
                )
                print_query_result("Top average speeds across all sessions", [
                    {"session": row[0], "driver_number": row[1], "avg_speed": row[2], "max_speed": row[3]}
                    for row in cur.fetchall()
                ])

                cur.execute(
                    """
                    SELECT s.event_name,
                           COUNT(*) AS lap_rows,
                           ROUND(AVG(l.lap_time_seconds), 3) AS avg_lap_time_seconds
                    FROM (
                        SELECT session_key, driver, lap_number,
                               EXTRACT(EPOCH FROM lap_time) AS lap_time_seconds
                        FROM laps
                    ) l
                    JOIN sessions s ON s.session_key = l.session_key
                    GROUP BY s.event_name
                    ORDER BY avg_lap_time_seconds ASC
                    LIMIT 10
                    """
                )
                print_query_result("Average lap times by event", [
                    {"event_name": row[0], "lap_rows": row[1], "avg_lap_time_seconds": row[2]}
                    for row in cur.fetchall()
                ])

            cur.execute(
                """
                SELECT session, driver_number, COUNT(*) AS rows,
                       ROUND(AVG(speed)::numeric, 2) AS avg_speed
                FROM car_telemetry
                GROUP BY session, driver_number
                ORDER BY rows DESC
                LIMIT 5
                """
            )
            print_query_result("Largest driver telemetry samples", [
                {"session": row[0], "driver_number": row[1], "rows": row[2], "avg_speed": row[3]}
                for row in cur.fetchall()
            ])


if __name__ == "__main__":
    main()
