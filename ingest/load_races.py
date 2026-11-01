import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from ingest.helper import DB_DSN
    from ingest.load_laps import main as load_laps_main
    from ingest.load_sessions import main as load_sessions_main
    from ingest.load_telemetry import main as load_telemetry_main
    from ingest.load_weather import main as load_weather_main
except ModuleNotFoundError:
    from load_laps import main as load_laps_main
    from load_sessions import main as load_sessions_main
    from load_telemetry import main as load_telemetry_main
    from load_weather import main as load_weather_main


def main():
    load_sessions_main()
    load_laps_main()
    load_weather_main()
    load_telemetry_main()


if __name__ == "__main__":
    main()
