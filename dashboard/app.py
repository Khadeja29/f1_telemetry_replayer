import os
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import psycopg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.helper import DB_DSN

st.set_page_config(page_title="F1 Telemetry Dashboard", page_icon="🏎️", layout="wide")
st.title("🏎️ F1 Telemetry Dashboard")


@st.cache_data(ttl=60)
def load_sessions():
    with psycopg.connect(DB_DSN) as conn:
        return pd.read_sql_query(
            "SELECT session_key, year, round, event_name, country, circuit, session_type, start_time FROM sessions ORDER BY start_time",
            conn,
        )


@st.cache_data(ttl=60)
def load_laps(session_key: str):
    with psycopg.connect(DB_DSN) as conn:
        return pd.read_sql_query(
            """
            SELECT driver,
                   lap_number,
                   lap_start,
                   lap_start + lap_time AS lap_end,
                   extract(epoch from lap_time)::float8 AS lap_seconds,
                   speed_st
            FROM laps
            WHERE session_key = %s AND lap_time IS NOT NULL
            ORDER BY driver, lap_number
            """,
            conn,
            params=(session_key,),
        )


@st.cache_data(ttl=60)
def load_lap_telemetry(session_key: str, driver: str, lap_start, lap_end):
    with psycopg.connect(DB_DSN) as conn:
        return pd.read_sql_query(
            """
            SELECT time, speed, throttle, brake, gear
            FROM car_telemetry
            WHERE session = %s AND driver = %s AND time BETWEEN %s AND %s
            ORDER BY time
            """,
            conn,
            params=(session_key, driver, lap_start, lap_end),
        )


@st.cache_data(ttl=60)
def load_driver_summary(session_key: str):
    with psycopg.connect(DB_DSN) as conn:
        return pd.read_sql_query(
            """
            SELECT driver,
                   ROUND(AVG(speed)::numeric, 2) AS avg_speed,
                   ROUND(AVG(rpm)::numeric, 2) AS avg_rpm,
                   MAX(speed) AS max_speed
            FROM car_telemetry
            WHERE session = %s
            GROUP BY driver
            ORDER BY avg_speed DESC
            """,
            conn,
            params=(session_key,),
        )


@st.cache_data(ttl=60)
def load_weather_summary(session_key: str):
    with psycopg.connect(DB_DSN) as conn:
        return pd.read_sql_query(
            """
            SELECT time, air_temp, track_temp, humidity, pressure, wind_speed, rainfall
            FROM weather
            WHERE session_key = %s
            ORDER BY time
            LIMIT 100
            """,
            conn,
            params=(session_key,),
        )


sessions = load_sessions()

if sessions.empty:
    st.warning("No session data loaded yet. Run the ingestion scripts first.")
    st.stop()

session_options = sessions["session_key"].tolist()
session_labels = {
    row.session_key: f"{row.event_name} {row.year}"
    for row in sessions.itertuples()
}
selected_session = st.selectbox(
    "Pick a session",
    session_options,
    index=min(0, len(session_options) - 1),
    format_func=lambda key: session_labels[key],
)
selected_row = sessions[sessions["session_key"] == selected_session].iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Year", int(selected_row["year"]))
col2.metric("Round", int(selected_row["round"]))
col3.metric("Event", str(selected_row["event_name"]))
col4.metric("Circuit", str(selected_row["circuit"]))

laps = load_laps(str(selected_session))
driver_summary = load_driver_summary(str(selected_session))
weather = load_weather_summary(str(selected_session))

st.subheader("Session overview")
summary_cols = st.columns(4)
summary_cols[0].metric("Laps", len(laps))
summary_cols[1].metric("Drivers", driver_summary["driver"].nunique())
summary_cols[2].metric("Avg speed", f"{driver_summary['avg_speed'].mean():.2f} km/h")
summary_cols[3].metric("Avg RPM", f"{driver_summary['avg_rpm'].mean():.2f}")

st.subheader("Driver performance")
if not driver_summary.empty:
    st.bar_chart(driver_summary.set_index("driver")["avg_speed"])
    st.dataframe(driver_summary, use_container_width=True)
else:
    st.info("No telemetry rows for this session. Run the telemetry loader for it, or pick another session.")

def format_lap_time(seconds: float) -> str:
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)}:{rest:06.3f}"


def pick_lap(driver: str, key: str):
    driver_laps = laps[laps["driver"] == driver]
    labels = {
        row.lap_number: f"Lap {row.lap_number} · {format_lap_time(row.lap_seconds)}"
        for row in driver_laps.itertuples()
    }
    options = driver_laps["lap_number"].tolist()
    fastest_number = int(driver_laps.loc[driver_laps["lap_seconds"].idxmin(), "lap_number"])
    number = st.selectbox(
        "Lap",
        options,
        index=options.index(fastest_number),
        format_func=lambda n: labels[n],
        key=key,
    )
    return driver_laps[driver_laps["lap_number"] == number].iloc[0]


def lap_trace(driver: str, lap) -> pd.DataFrame:
    telemetry = load_lap_telemetry(
        str(selected_session),
        driver,
        pd.Timestamp(lap["lap_start"]).to_pydatetime(),
        pd.Timestamp(lap["lap_end"]).to_pydatetime(),
    )
    if telemetry.empty:
        return pd.DataFrame(columns=["speed", "throttle", "brake"])
    telemetry["time"] = pd.to_datetime(telemetry["time"])
    telemetry["seconds_into_lap"] = (telemetry["time"] - telemetry["time"].min()).dt.total_seconds()
    # Brake is true/false; 0/1 lets it be plotted and averaged like the other traces.
    telemetry["brake"] = telemetry["brake"].astype(float)
    return telemetry.set_index("seconds_into_lap")[["speed", "throttle", "brake"]]


def align_traces(traces: dict, step: float = 0.25) -> dict:
    # Put every lap on the same time grid so the charts line up.
    # Past the end of a lap, values are left empty instead of repeating the last one.
    longest = max(trace.index.max() for trace in traces.values())
    grid = np.arange(0, longest, step)
    aligned = {}
    for label, trace in traces.items():
        frame = pd.DataFrame(index=pd.Index(grid, name="seconds"))
        for column in trace.columns:
            values = np.interp(grid, trace.index.values, trace[column].values)
            values[grid > trace.index.max()] = np.nan
            frame[column] = values
        aligned[label] = frame.reset_index()
    return aligned


def signals_chart(aligned: dict, signals=("Speed", "Throttle", "Brake")):
    # Speed uses the left axis (km/h). Throttle and brake share the right axis (0-100),
    # with brake scaled to 100 when on so it reads on the same scale as the pedal.
    pieces = []
    for label, frame in aligned.items():
        for column, name, axis in (("speed", "Speed", "speed"), ("throttle", "Throttle", "pedal"), ("brake", "Brake", "pedal")):
            values = frame[column] * 100 if column == "brake" else frame[column]
            pieces.append(
                pd.DataFrame(
                    {
                        "seconds": frame["seconds"],
                        "line": f"{label} · {name}",
                        "signal": name,
                        "axis": axis,
                        "value": values,
                    }
                )
            )
    long = pd.concat(pieces).dropna(subset=["value"])
    long = long[long["signal"].isin(signals)]

    base = alt.Chart(long).encode(
        x=alt.X("seconds:Q", title="Seconds into lap"),
        color=alt.Color("line:N", title=None),
        strokeDash=alt.StrokeDash("signal:N", title=None),
    )
    speed = base.transform_filter(alt.datum.axis == "speed").mark_line().encode(
        y=alt.Y("value:Q", title="Speed (km/h)"),
    )
    pedals = base.transform_filter(alt.datum.axis == "pedal").mark_line().encode(
        y=alt.Y("value:Q", title="Throttle (%) · brake on = 100", scale=alt.Scale(domain=[0, 100])),
    )
    return alt.layer(speed, pedals).resolve_scale(y="independent").properties(height=400)


drivers_list = sorted(laps["driver"].unique()) if not laps.empty else []

st.subheader("Lap explorer")
if laps.empty:
    st.info("No lap data for this session. Run the lap loader for it, or pick another session.")
else:
    explorer_driver = st.selectbox("Driver", drivers_list, key="explorer_driver")
    explorer_lap = pick_lap(explorer_driver, "explorer_lap")
    trace = lap_trace(explorer_driver, explorer_lap)
    if trace.empty:
        st.info("No telemetry rows inside this lap's time window.")
    else:
        explorer_label = f"{explorer_driver} lap {explorer_lap['lap_number']}"
        st.caption("Speed on the left axis. Throttle and brake on the right axis: brake shows as 100 when on.")
        st.altair_chart(signals_chart(align_traces({explorer_label: trace})))

st.subheader("Driver comparison")
if laps.empty:
    st.info("No lap data for this session.")
else:
    col_a, col_b = st.columns(2)
    with col_a:
        driver_a = st.selectbox("Driver A", drivers_list, index=0, key="compare_driver_a")
        lap_a = pick_lap(driver_a, "compare_lap_a")
    with col_b:
        driver_b = st.selectbox("Driver B", drivers_list, index=min(1, len(drivers_list) - 1), key="compare_driver_b")
        lap_b = pick_lap(driver_b, "compare_lap_b")

    label_a = f"A: {driver_a} (lap {lap_a['lap_number']})"
    label_b = f"B: {driver_b} (lap {lap_b['lap_number']})"
    trace_a = lap_trace(driver_a, lap_a)
    trace_b = lap_trace(driver_b, lap_b)

    if trace_a.empty or trace_b.empty:
        st.info("One of these laps has no telemetry rows. Pick a different lap.")
    else:
        gap = lap_a["lap_seconds"] - lap_b["lap_seconds"]
        faster = driver_a if gap < 0 else driver_b
        st.metric("Lap time gap", f"{abs(gap):.3f} s", help=f"{faster} is faster over these two laps")

        signals_shown = st.multiselect(
            "Show",
            ["Speed", "Throttle", "Brake"],
            default=["Speed", "Throttle", "Brake"],
            key="compare_signals",
        )
        st.caption(
            "Speed on the left axis (solid lines). Throttle (dotted) and brake (dashed) on the right axis, "
            "with brake at 100 when on. Where a driver's brake line jumps up, they have hit the brakes."
        )
        if signals_shown:
            st.altair_chart(signals_chart(align_traces({label_a: trace_a, label_b: trace_b}), signals_shown))
        else:
            st.info("Pick at least one signal to show.")

st.subheader("Speed trap vs lap time")
speed_trap_laps = laps.dropna(subset=["speed_st"])
if speed_trap_laps.empty:
    st.info("No speed-trap readings for this session.")
else:
    st.metric("Correlation (speed trap vs lap time)", f"{speed_trap_laps['speed_st'].corr(speed_trap_laps['lap_seconds']):.2f}")
    st.scatter_chart(speed_trap_laps, x="speed_st", y="lap_seconds")
    st.caption("Each dot is one lap. A correlation near -1 means faster cars on the straight tend to set shorter lap times.")

st.subheader("Weather")
if not weather.empty:
    st.line_chart(weather.set_index("time")[["air_temp", "track_temp", "wind_speed"]])
    st.dataframe(weather.head(20), use_container_width=True)
