"""SpotOn web client (Streamlit). A thin client over the SpotOn API.

Run (from the repository root, with the API already running):
    uv run --group web streamlit run frontend/app.py
API location: SPOTON_API_URL (default http://127.0.0.1:8000).
"""

import streamlit as st

from client import get_client

st.set_page_config(page_title="SpotOn", page_icon="💪", layout="centered")

api = get_client()
if api.logged_in:
    pages = [
        st.Page("pages/today.py", title="Today", icon=":material/today:", default=True),
        st.Page("pages/log_meal.py", title="Log meal", icon=":material/photo_camera:"),
        st.Page("pages/coach.py", title="Coach", icon=":material/forum:"),
        st.Page("pages/plan.py", title="My foods", icon=":material/restaurant_menu:"),
        st.Page("pages/progress.py", title="Progress", icon=":material/monitoring:"),
        st.Page("pages/history.py", title="History", icon=":material/insights:"),
        st.Page("pages/profile.py", title="Profile", icon=":material/person:"),
    ]
else:
    pages = [st.Page("pages/login.py", title="Sign in", icon=":material/login:", default=True)]

st.navigation(pages, position="top").run()
st.caption("AI nutrition values are estimates; check them before saving. Not medical advice.")
