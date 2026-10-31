-- Plain table, not a hypertable: ~1,200 laps per race is tiny, an
CREATE TABLE laps (
    session_key    TEXT        NOT NULL REFERENCES sessions (session_key),
    driver         TEXT        NOT NULL,
    driver_number  SMALLINT,
    team           TEXT,
    lap_number     SMALLINT    NOT NULL,
    lap_start      TIMESTAMPTZ,
    lap_time       INTERVAL,
    sector1_time   INTERVAL,
    sector2_time   INTERVAL,
    sector3_time   INTERVAL,
    speed_i1       REAL,                      -- speed trap: intermediate 1
    speed_i2       REAL,                      -- speed trap: intermediate 2
    speed_fl       REAL,                      -- speed trap: finish line
    speed_st       REAL,                      -- speed trap: longest straight
    compound       TEXT,
    tyre_life      SMALLINT,
    fresh_tyre     BOOLEAN,
    stint          SMALLINT,
    pit_in         BOOLEAN,
    pit_out        BOOLEAN,
    position       SMALLINT,
    track_status   TEXT,
    is_accurate    BOOLEAN,
    deleted        BOOLEAN,
    PRIMARY KEY (session_key, driver, lap_number)
);
