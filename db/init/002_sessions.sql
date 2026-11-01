CREATE TABLE sessions (
    session_key    TEXT        PRIMARY KEY,   -- e.g. '2024_05_R' (year_round_type)
    year           SMALLINT    NOT NULL,
    round          SMALLINT    NOT NULL,
    event_name     TEXT        NOT NULL,
    country        TEXT,
    circuit        TEXT,
    session_type   TEXT        NOT NULL,      -- 'R' race, 'Q' qualifying, ...
    start_time     TIMESTAMPTZ NOT NULL,
    end_time       TIMESTAMPTZ,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
