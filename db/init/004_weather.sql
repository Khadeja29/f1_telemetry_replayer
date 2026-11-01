CREATE TABLE weather (
    time            TIMESTAMPTZ NOT NULL,
    session_key     TEXT        NOT NULL REFERENCES sessions (session_key),
    air_temp        REAL,
    track_temp      REAL,
    humidity        REAL,
    pressure        REAL,
    rainfall        BOOLEAN,
    wind_speed      REAL,
    wind_direction  SMALLINT
);

SELECT create_hypertable('weather', by_range('time'));

-- Required for the loader's ON CONFLICT (time, session_key) DO NOTHING.
-- Without this index, re-running a load inserts every row again as a duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS weather_time_session_uq
    ON weather (time, session_key);
