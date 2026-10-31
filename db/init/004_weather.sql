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
