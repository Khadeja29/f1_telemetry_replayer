CREATE TABLE car_telemetry (
    time           TIMESTAMPTZ NOT NULL,
    session_time   INTERVAL,
    slice_time     INTERVAL,
    session        TEXT        NOT NULL,
    driver         TEXT        NOT NULL,
    driver_number  SMALLINT,
    speed          REAL,
    rpm            INTEGER,
    gear           SMALLINT,
    throttle       REAL,
    brake          BOOLEAN,
    drs            SMALLINT,
    source         TEXT,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

SELECT create_hypertable('car_telemetry', by_range('time'));

-- Required for the loader's ON CONFLICT (time, session, driver_number) DO NOTHING.
-- Without this index, re-running a load inserts every row again as a duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS car_telemetry_time_session_driver_uq
    ON car_telemetry (time, session, driver_number);
