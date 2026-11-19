"""History (PRD T-11): day / week / month / year from your start date, with charts."""

import pandas as pd
import streamlit as st

from client import get_client
from components import call, need_profile_notice

api = get_client()
st.title("History")

profile = call(api.profile)
if profile is None:
    need_profile_notice()
    st.stop()
targets = profile["targets"]

period = st.segmented_control(
    "View", ["day", "week", "month", "year"], default="day", format_func=str.title, key="history_period"
)
hist = call(api.history, period or "day")
if not hist:
    st.stop()

c = st.columns(3)
c[0].metric("Days logged", hist["days_logged"])
c[1].metric("Since", pd.Timestamp(hist["start"]).strftime("%d %b %Y"))
trend = hist["weight_trend"]
if trend:
    first, last = trend[0]["trend_kg"], trend[-1]["trend_kg"]
    c[2].metric("Trend weight", f"{last:.1f} kg", delta=f"{last - first:+.1f} kg", delta_color="inverse")

rows = pd.DataFrame(hist["rows"])
if rows.empty:
    st.caption("No data yet.")
    st.stop()
x = "day" if period in (None, "day") else period
rows[x] = pd.to_datetime(rows[x])
rows = rows.set_index(x)
logged = rows[rows["kcal"] > 0] if period in (None, "day") else rows

st.subheader("Calories")
st.line_chart(logged[["kcal"]].assign(target=targets["kcal"]).rename(columns={"kcal": "eaten"}))
st.subheader("Protein (g)")
st.line_chart(logged[["protein"]].assign(target=targets["protein_g"]).rename(columns={"protein": "eaten"}))
st.subheader("Steps")
st.bar_chart(rows[["steps"]])

weights = rows["weight_kg" if "weight_kg" in rows else "avg_weight_kg"].dropna()
if not weights.empty:
    st.subheader("Weight (kg)")
    w = pd.DataFrame({"weight": weights})
    if trend and period in (None, "day"):
        t = pd.DataFrame(trend).assign(day=lambda d: pd.to_datetime(d["day"])).set_index("day")["trend_kg"]
        w = w.join(t.rename("trend"), how="outer")
    st.line_chart(w)
    st.caption("The trend line smooths out day-to-day water swings.")

with st.expander("Table"):
    st.dataframe(rows, width="stretch")
