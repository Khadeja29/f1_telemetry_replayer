# F1 Telemetry & Historical Replayer

Replays 6–12 months of historical Formula 1 telemetry through Kafka as if the races were happening live, and stores it in TimescaleDB for time-series analysis.

## Architecture

```
F1 telemetry (CSV/Parquet)  ──►  Python producer  ──►  Kafka  ──►  Python consumer  ──►  TimescaleDB
   (fastf1 / Kaggle)            (row-by-row replay)                                      (hypertable)
```

- **Data:** ~10 Hz car telemetry: speed, gear, throttle %, brake, DRS status.
- **Producer:** reads the historical partition in time order and publishes each row to Kafka, so the races replay as if they were live.
- **Storage:** PostgreSQL + TimescaleDB hypertables, built for heavy time-series writes and analytics queries.
- **Local dev:** everything runs with Docker Compose.

## Status

🚧 Setting up.
