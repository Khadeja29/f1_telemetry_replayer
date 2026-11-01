# F1 Telemetry Replayer

A data pipeline and dashboard for Formula 1 race telemetry. It loads the 2024 season from the [OpenF1](https://openf1.org) API into TimescaleDB, then lets you explore each race: lap by lap, driver against driver, and across the whole season.

## Highlights

- **Full race data:** lap times, sector times, speed traps, weather, and about 4 samples per second of car telemetry (speed, throttle, brake, gear, RPM, DRS) for every car.
- **Lap explorer:** replay one driver's lap as speed, throttle and brake against time.
- **Driver comparison:** overlay two laps, with a toggle to show any combination of speed, throttle and brake, and the lap time gap between them.
- **Finding in the data:** across the 959 laps of the 2024 Bahrain Grand Prix, straight-line speed and lap time have a correlation of **-0.75**. Cars that are faster on the straight tend to set shorter lap times.
- **Safe to re-run:** every table has a unique index on its key columns, so re-running a loader skips rows it already has.

## How it fits together

```
OpenF1 API  ──►  ingest/ scripts  ──►  TimescaleDB  ──►  Streamlit dashboard
                 (Python)              (Postgres +        (dashboard/app.py)
                                        hypertables)
```

- **Storage:** PostgreSQL with TimescaleDB. Telemetry and weather are hypertables, which suit time-series queries.
- **Ingestion:** Python scripts fetch each race from OpenF1 and insert it with `ON CONFLICT` clauses, so loads can be repeated.
- **Dashboard:** Streamlit and Altair, reading straight from the database.
- **Local setup:** Docker Compose runs the database and the dashboard.

## Data

| Table | What it holds | Key |
|---|---|---|
| `sessions` | One row per race: year, round, event, circuit, start time | `session_key` |
| `laps` | One row per driver per lap: lap and sector times, speed traps, tyre info | `(session_key, driver, lap_number)` |
| `car_telemetry` | Car telemetry, about 4 samples per second per car | `(time, session, driver_number)` |
| `weather` | Air and track temperature, humidity, pressure, wind, rain | `(time, session_key)` |

The current load covers the 2024 race sessions. Practice and qualifying are not loaded yet.

## Quick start

You need Docker and Python 3.12.

1. **Set up the environment file:**

   ```bash
   cp .env.example .env
   ```

   Change `PGPASSWORD` to your own value.

2. **Start the database.** The first run creates the tables and indexes from `db/init/`:

   ```bash
   docker compose up -d timescaledb
   ```

3. **Install the Python dependencies:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Load the data:**

   ```bash
   python -m ingest.load_races
   ```

   This loads sessions, laps, weather and telemetry for every 2024 race. Telemetry takes the longest, because OpenF1 limits how fast requests can be made.

5. **Open the dashboard:**

   ```bash
   docker compose up -d --build dashboard
   ```

   Then go to http://localhost:8501. To run it without Docker, use `streamlit run dashboard/app.py` instead.

### Loading part of the data

```bash
python -m ingest.load_sessions     # race list
python -m ingest.load_laps         # laps
python -m ingest.load_weather      # weather
python -m ingest.load_telemetry    # car telemetry
```

`load_telemetry` also accepts `--session-key <key>` to load one race, and `--limit <n>` to load only the first n races.

## The dashboard

**Session overview.** Year, round, event, circuit, lap count, driver count, and average speed and RPM across the race.

**Driver performance.** Average speed, average RPM and top speed for each driver over the whole race, ranked by average speed.

**Lap explorer.** Pick a driver and a lap (the fastest is selected by default). Speed is on the left axis. Throttle and brake are on the right axis, with brake shown as 100 when on.

**Driver comparison.** Pick two drivers and a lap for each. The chart overlays both laps, and a **Show** toggle lets you hide any of speed, throttle or brake to reduce clutter. The lap time gap is shown above the chart.

**Speed trap vs lap time.** One dot per lap, with the correlation between speed trap and lap time.

**Weather.** Air temperature, track temperature and wind speed through the race.

## Understanding the signals

- **Speed (km/h):** how fast the car is going. Flat tops are straights, dips are corners.
- **Throttle (%):** how far the accelerator is pressed. 100 is flat out.
- **Brake:** on or off. It switches on before a corner and off as the driver gets back on the throttle.
- **Gear:** 1 to 8. Low gears for corners, high gears for straights.
- **RPM:** engine revolutions per minute. It rises and falls with gear, so it shows a sawtooth pattern.
- **DRS:** a rear-wing flap that opens on some straights to reduce drag. The raw values are codes, not a simple on/off.

## Command-line summary

```bash
python -m insights.insights                      # row counts and summary queries
python -m insights.insights --session-key 9472   # the same, for one race
```

## Project layout

```
compose.yaml          Docker services: TimescaleDB and the dashboard
db/init/              Table and index definitions, run when the database is first created
ingest/               Scripts that load data from OpenF1 into the database
insights/             Summary queries printed to the terminal
dashboard/            Streamlit app and its Dockerfile
```

## Notes and limitations

- **Schema changes only apply to new databases.** `db/init/` runs only when the database is first created. To apply a change to an existing database, run the statement by hand. `docker compose down -v` deletes all loaded data, so use it only when you want to start over.
- **Race data only.** The loaders keep only race sessions. Adding practice and qualifying means changing the session filter in `ingest/helper.py` and `ingest/load_sessions.py`.
- **Brake is on/off.** The data does not show how hard the driver braked.
- **Throttle can exceed 100** in some samples, so treat 100 as "full throttle" rather than a hard maximum.
- **Correlation is not causation.** The speed trap and lap time chart includes pit and safety-car laps, which widen the spread.

