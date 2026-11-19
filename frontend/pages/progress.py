"""Progress (PRD P-02..P-06): weekly review, weight trend, learned maintenance,
predictions (always ranges) and body measurements."""

import datetime as dt

import pandas as pd
import streamlit as st

from client import get_client
from components import call, need_profile_notice

api = get_client()
st.title("Progress")

data = call(api.progress, quiet_codes=("profile_required",))
if data is None:
    need_profile_notice()
    st.stop()
weekly = call(api.weekly_review) or {}


def fmt_day(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%d %b")


# --- Weekly review --------------------------------------------------------------------
st.subheader("Weekly review")
review = weekly.get("review")
if not review:
    st.caption(f"Your first weekly review arrives on {dt.date.fromisoformat(weekly['next_review_on']):%A %d %b}.")
else:
    s = review["summary"]
    with st.container(border=True):
        st.markdown(f"**Week of {fmt_day(s['week_start'])} – {fmt_day(s['week_end'])}**")
        c = st.columns(4)
        c[0].metric("Days logged", f"{s['days_logged']} / 7")
        c[1].metric("Avg calories", f"{s['avg_kcal']:,}" if s["avg_kcal"] else "–", help=f"Target {s['kcal_target']:,}")
        c[2].metric("Protein days", f"{s['protein_hit_days']} / 7", help=f"Days at 90%+ of {s['protein_target_g']} g")
        change = s.get("trend_change_kg")
        c[3].metric("Trend", f"{s['trend_end_kg']:.1f} kg" if s["trend_end_kg"] else "–",
                    delta=f"{change:+.2f} kg" if change is not None else None, delta_color="off")  # fmt: skip
        if s.get("waist_change_cm") is not None:
            st.caption(f"Waist: {s['waist_change_cm']:+.1f} cm this week")
        for note in s.get("notes", []):
            st.markdown(f"- {note}")
        proposal = review.get("proposal")
        if proposal:
            st.info(f"**Suggested change:** {proposal['text']}  \n{proposal['reason']}")
            if review["decision"]:
                st.caption(f"You {review['decision']} this on {fmt_day(review['decided_at'][:10])}.")
            else:
                a, k = st.columns(2)
                if a.button("✅ Accept", type="primary", width="stretch"):
                    if call(api.decide_review, review["id"], True):
                        st.toast("Targets updated")
                        st.rerun()
                if k.button("Keep as is", width="stretch"):
                    if call(api.decide_review, review["id"], False):
                        st.rerun()

# --- Weight -------------------------------------------------------------------------------
st.subheader("Weight")
w = data["weight"]
c = st.columns(3)
c[0].metric("Trend weight", f"{w['trend_kg']:.1f} kg" if w["trend_kg"] else "–")
c[1].metric("Last 4 weeks", f"{w['trend_change_4w_kg']:+.1f} kg" if w["trend_change_4w_kg"] is not None else "–")
if data["in_weeks"]:
    iw = data["in_weeks"]
    c[2].metric(f"In {iw['weeks']} weeks", f"{iw['low_kg']:.1f}–{iw['high_kg']:.1f} kg")
if w["series"]:
    chart = pd.DataFrame(w["series"]).assign(day=lambda d: pd.to_datetime(d["day"])).set_index("day")
    st.line_chart(chart.rename(columns={"kg": "weigh-in", "trend_kg": "trend"}))
    st.caption("The trend smooths out day-to-day water swings; it's what the targets and predictions use.")
if data["prediction"]:
    st.info(f"🎯 {data['prediction']['message']}")
else:
    st.caption("Add a goal weight on the Profile page to see when you're likely to reach it.")

# --- Maintenance -----------------------------------------------------------------------------
st.subheader("Maintenance calories")
m = data["maintenance"]
c = st.columns(2)
c[0].metric("Learned" if m["active"] else "Formula (for now)", f"{m['kcal']:,.0f} kcal")
c[1].metric("Formula estimate", f"{m['formula_kcal']:,.0f} kcal")
st.caption(m["explanation"])
if len(m["history"]) > 1:
    hist = pd.DataFrame(m["history"]).assign(week=lambda d: pd.to_datetime(d["week_start"])).set_index("week")
    st.line_chart(hist[["kcal", "observed"]].rename(columns={"kcal": "learned", "observed": "data says"}))

# --- Measurements ----------------------------------------------------------------------------
st.subheader("Measurements")
with st.form("measure"):
    a, b, c = st.columns(3)
    waist = a.number_input("Waist (cm)", 40.0, 250.0, value=None, step=0.5)
    hip = b.number_input("Hip (cm)", 40.0, 250.0, value=None, step=0.5)
    fat = c.number_input("Body fat %", 3.0, 70.0, value=None, step=0.5)
    if st.form_submit_button("Save measurements") and any(v is not None for v in (waist, hip, fat)):
        if call(api.log_measurement, {"waist_cm": waist, "hip_cm": hip, "body_fat_pct": fat}):
            st.toast("Saved ✅")
            st.rerun()
if data["measurements"]:
    meas = pd.DataFrame(data["measurements"]).assign(day=lambda d: pd.to_datetime(d["day"])).set_index("day")
    st.line_chart(meas[["waist_cm", "hip_cm"]].dropna(how="all"))
    st.caption("Body fat % you enter here is also used to calculate your BMR.")
