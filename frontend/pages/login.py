"""Sign in / create account."""

import streamlit as st

from client import get_client
from components import call

api = get_client()
MIN_PASSWORD = 8  # matches the API's UserCreate.password rule
st.title("💪 SpotOn")
st.write("Your AI personal trainer: snap a meal, see what's left today, get a next step.")

sign_in, sign_up = st.tabs(["Sign in", "Create account"])

with sign_in, st.form("login"):
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    if st.form_submit_button("Sign in", type="primary", width="stretch") and email and password:
        call(api.login, email, password)
        if api.logged_in:
            st.rerun()

with sign_up, st.form("register"):
    email = st.text_input("Email", key="reg_email")
    password = st.text_input("Password (at least 8 characters)", type="password", key="reg_password")
    st.caption("SpotOn is for adults (18+). Your data is yours: export it any time from Profile.")
    if st.form_submit_button("Create account", type="primary", width="stretch") and email and password:
        if len(password) < MIN_PASSWORD:
            st.error(f"Password must be at least {MIN_PASSWORD} characters (yours has {len(password)}).")
            st.stop()
        call(api.register, email, password)
        if api.logged_in:
            st.session_state["new_account"] = True
            st.rerun()
