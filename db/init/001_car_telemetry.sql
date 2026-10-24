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