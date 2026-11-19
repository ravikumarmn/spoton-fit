"""Profile and targets (PRD T-01, T-02), remembered foods, data export, sign out."""

import streamlit as st

from client import get_client
from components import call

api = get_client()
st.title("Profile")

profile = call(api.profile) or {}
if not profile:
    st.info("Welcome! Fill this in once; SpotOn works out your calorie and protein targets from it.")

GOALS = {"lose_fat": "Lose fat", "build_muscle": "Build muscle", "maintain": "Maintain"}
ACTIVITY = {
    "sedentary": "Sedentary (desk job, little exercise)",
    "light": "Light (training 1–3 days/week)",
    "moderate": "Moderate (3–5 days/week)",
    "active": "Active (6–7 days/week)",
}

with st.form("profile"):
    a, b = st.columns(2)
    age = a.number_input("Age", 18, 100, profile.get("age", 30))
    sex = b.selectbox("Sex", ["male", "female"], index=["male", "female"].index(profile.get("sex", "male")))
    height = a.number_input("Height (cm)", 100.0, 250.0, float(profile.get("height_cm", 170.0)), step=0.5)
    weight = b.number_input("Weight (kg)", 30.0, 300.0, float(profile.get("weight_kg", 70.0)), step=0.1)
    goal = a.selectbox(
        "Goal", list(GOALS), index=list(GOALS).index(profile.get("goal", "lose_fat")), format_func=GOALS.get
    )
    activity = b.selectbox(
        "Activity", list(ACTIVITY), index=list(ACTIVITY).index(profile.get("activity", "sedentary")),
        format_func=ACTIVITY.get,
    )  # fmt: skip
    body_fat = a.number_input("Body fat % (optional)", 3.0, 70.0, profile.get("body_fat_pct"), step=0.5)
    goal_weight = b.number_input("Goal weight kg (optional)", 30.0, 300.0, profile.get("goal_weight_kg"), step=0.5)
    steps = a.number_input("Usual daily steps", 0, 50_000, profile.get("baseline_steps", 5000), step=500)
    if st.form_submit_button("Save profile", type="primary", width="stretch"):
        body = {
            "age": int(age),
            "sex": sex,
            "height_cm": height,
            "weight_kg": weight,
            "goal": goal,
            "activity": activity,
            "body_fat_pct": body_fat,
            "goal_weight_kg": goal_weight,
            "baseline_steps": int(steps),
        }
        if call(api.save_profile, body):
            st.toast("Profile saved ✅")
            st.rerun()

for w in profile.get("warnings", []):
    st.warning(w)

if profile:
    t = profile["targets"]
    st.subheader("Your daily targets")
    c = st.columns(3)
    c[0].metric("Calories", f"{t['kcal']:,}", help=f"Never below the safety floor of {t['kcal_floor']:,} kcal")
    c[1].metric("Protein", f"{t['protein_g']} g")
    c[2].metric("Steps", f"{t['steps']:,}")
    c = st.columns(3)
    c[0].metric("BMR", f"{t['bmr']:,.0f} kcal")
    c[1].metric("Maintenance", f"{t['maintenance']:,.0f} kcal")
    c[2].metric("Water", f"{t['water_ml'] / 1000:.1f} L")
    st.caption(f"BMI {t['bmi']} · fat {t['fat_g']} g · carbs {t['carbs_g']} g · fibre {t['fibre_g']} g")

st.subheader("Foods SpotOn remembers")
memory = call(api.food_memory) or []
if not memory:
    st.caption("When you correct a food's per-unit values while logging, SpotOn remembers them here.")
for f in memory:
    cols = st.columns([5, 1])
    per = f"{f['kcal']:.0f} kcal · {f['protein']:.1f} g protein"
    cols[0].markdown(f"**{f['name']}** (per {f['unit']}): {per} · used {f['times_used']}×")
    if cols[1].button("Forget", key=f"forget{f['id']}"):
        call(api.forget_food, f["id"])
        st.rerun()

st.subheader("Your data")
if st.button("Prepare export"):
    st.session_state["export_json"] = call(api.export, "json")
    st.session_state["export_csv"] = call(api.export, "csv")
if st.session_state.get("export_json"):
    d = st.columns(2)
    d[0].download_button("Download JSON", st.session_state["export_json"], "spoton-export.json", "application/json")
    d[1].download_button("Download CSV (zip)", st.session_state["export_csv"], "spoton-export.zip", "application/zip")

st.divider()
if st.button("Sign out"):
    api.logout()
    for k in list(st.session_state):
        if k != "_http":
            del st.session_state[k]
    st.rerun()
