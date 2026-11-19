"""Coach chat (PRD C-01, C-05) and meal suggestions (C-02).

Replies stream in word by word (Server-Sent Events). Today's conversation is loaded
from the API, so it survives page refreshes and API restarts.
"""

import streamlit as st

from client import get_client
from components import call, item_line, show_error, start_draft, today_id

api = get_client()
st.title("Coach")

# --- Suggestions ------------------------------------------------------------------------
with st.expander("🍽️ What should I eat next?", expanded=False):
    mode = st.segmented_control(
        "From", ["my_foods", "ideal"], default="my_foods", key="suggest_mode",
        format_func={"my_foods": "My Foods", "ideal": "Any food"}.get,
    )  # fmt: skip
    if st.button("Suggest two options", width="stretch"):
        with st.spinner("Thinking about what fits…"):
            st.session_state["suggestions"] = call(api.suggestions, mode or "my_foods")
    sug = st.session_state.get("suggestions")
    if sug:
        st.caption(f"Left today: {sug['left']['kcal']:,.0f} kcal · {sug['left']['protein_g']:,.0f} g protein")
        if sug.get("note"):
            st.info(sug["note"])
        for n, opt in enumerate(sug["options"]):
            with st.container(border=True):
                fit = "✅ fits" if opt["fits"] else "⚠️ over budget"
                tot = opt["totals"]
                st.markdown(f"**{opt['title']}** · {tot['kcal']:.0f} kcal · {tot['protein']:.0f} g protein · {fit}")
                st.caption(opt["why"])
                for item in opt["items"]:
                    st.markdown(f"- {item_line(item)}")
                if st.button("Review & log this", key=f"use{n}"):
                    start_draft({"items": opt["items"], "meal_slot": None, "warnings": [], "oily_items": []}, "text")
                    st.switch_page("pages/log_meal.py")

# --- Chat ---------------------------------------------------------------------------------
thread = today_id()
if st.session_state.get("chat_thread") != thread:  # first visit today: load from the API
    st.session_state["chat"] = call(api.coach_thread, thread, quiet_codes=("ai_not_configured",)) or []
    st.session_state["chat_thread"] = thread
chat = st.session_state["chat"]

if not chat:
    st.caption(
        'Ask anything about today, e.g. "Can I have tea now?" or "I\'m at a biryani place, what should I order?"'
    )
for msg in chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask your coach"):
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        status = st.empty()
        result: dict = {}

        def tokens():
            for event, data in api.coach_stream(prompt, thread):
                if event == "status":
                    status.caption(f"Checking {data['tool'].replace('_', ' ')}…")
                elif event == "token":
                    status.empty()
                    yield data["text"]
                elif event in ("done", "error"):
                    result[event] = data

        try:
            streamed = st.write_stream(tokens())
        except Exception as e:
            show_error(e)
            streamed = None
        if "error" in result:
            st.error(result["error"]["message"])
        elif streamed is not None:
            reply = result.get("done", {}).get("reply") or streamed
            if result.get("done", {}).get("safety"):
                st.caption("This is a safety reply; SpotOn doesn't give diet advice for these situations.")
            chat.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])
