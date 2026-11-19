"""Today (PRD T-09, T-10): what's eaten, what's left, quick logs, today's meals."""

import datetime as dt

import streamlit as st

from client import get_client
from components import call, item_line, local_time, need_profile_notice, progress_row

api = get_client()

if st.session_state.pop("new_account", False):
    st.switch_page("pages/profile.py")

today = call(api.today, quiet_codes=("profile_required",))
if today is None:
    if api.logged_in and call(api.profile) is None:
        need_profile_notice()
    st.stop()

t, eaten, left = today["targets"], today["eaten"], today["left"]
st.title("Today")
st.caption(dt.date.fromisoformat(today["day"]).strftime("%A, %d %B"))

c = st.columns(3)
c[0].metric("Calories left", f"{left['kcal']:,.0f}", help=f"Target {t['kcal']:,} kcal (floor {t['kcal_floor']:,})")
c[1].metric("Protein left", f"{left['protein_g']:,.0f} g")
c[2].metric(
    "Burned so far",
    f"{today['burned_kcal_est']:,.0f} kcal",
    help="Estimate up to now: resting burn for the hours so far + steps + workouts. "
    "It grows through the day and is not added back to your food budget.",
)

weekly = call(api.weekly_review, quiet_codes=("profile_required",))
if weekly and weekly["pending_decision"]:
    with st.container(border=True):
        st.markdown(f"📅 **Your weekly review is ready**: {weekly['review']['proposal']['text']}")
        if st.button("See weekly review", type="primary"):
            st.switch_page("pages/progress.py")

for note in today.get("nudges", []):
    st.info(note, icon="📏")

progress_row("Calories", eaten["kcal"], t["kcal"], "kcal")
progress_row("Protein", eaten["protein_g"], t["protein_g"], "g")
progress_row("Carbs", eaten["carbs_g"], t["carbs_g"], "g")
progress_row("Fat", eaten["fat_g"], t["fat_g"], "g")
progress_row("Water", today["water_ml"], t["water_ml"], "ml")
progress_row("Steps", today["steps"], t["steps"], "")

st.subheader("Quick log")
q = st.columns(4)
if q[0].button("💧 +250 ml", width="stretch"):
    call(api.add_water, 250)
    st.rerun()
if q[1].button("💧 +500 ml", width="stretch"):
    call(api.add_water, 500)
    st.rerun()
if q[2].button("📷 Log meal", width="stretch", type="primary"):
    st.switch_page("pages/log_meal.py")
if q[3].button("💬 Ask coach", width="stretch"):
    st.switch_page("pages/coach.py")

with st.expander("Steps, weight and workouts"):
    with st.form("steps"):
        steps = st.number_input("Steps today", min_value=0, max_value=150_000, value=today["steps"], step=500)
        if st.form_submit_button("Save steps"):
            call(api.set_steps, today["day"], int(steps))
            st.rerun()
    with st.form("weight"):
        kg = st.number_input("Weight (kg)", min_value=30.0, max_value=300.0, value=None, step=0.1, format="%.1f")
        if st.form_submit_button("Save weight") and kg:
            call(api.log_weight, float(kg))
            st.rerun()
    with st.form("workout"):
        text = st.text_input("Workout", placeholder="15 min cycling, 40 min weights")
        if st.form_submit_button("Log workout") and text:
            rows = call(api.log_workout, text)
            if rows:
                st.toast(", ".join(f"{r['activity']}: {r['kcal']:.0f} kcal" for r in rows))
                st.rerun()

st.subheader("Meals")
meals = call(api.meals) or []
if not meals:
    st.caption("Nothing logged yet today.")
for m in meals:
    with st.container(border=True):
        when = local_time(m["eaten_at"])
        head, fav, again, delete = st.columns([6, 1, 1, 1])
        head.markdown(f"**{m['slot'].replace('_', ' ').title()}** · {when} · {m['totals']['kcal']:.0f} kcal")
        if fav.button("⭐" if m["is_favourite"] else "☆", key=f"fav{m['id']}", help="Favourite"):
            call(api.edit_meal, m["id"], {"is_favourite": not m["is_favourite"]})
            st.rerun()
        if again.button("🔁", key=f"rep{m['id']}", help="Log again now"):
            call(api.repeat_meal, m["id"])
            st.rerun()
        if delete.button("🗑️", key=f"del{m['id']}", help="Delete"):
            call(api.delete_meal, m["id"])
            st.rerun()
        for item in m["items"]:
            st.markdown(f"- {item_line(item)}")
