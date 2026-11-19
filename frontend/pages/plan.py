"""My Foods (PRD C-03) and food rules (C-04).

- My Foods: what you can actually get. Suggestions use only these (when available).
- Rules: write them in plain English; SpotOn shows how it understood them, you confirm,
  then they're checked against what you log, with gentle nudges on Today.
"""

import pandas as pd
import streamlit as st

from client import get_client
from components import SLOTS, call

api = get_client()
EFFORT = {"no_cook": "No cooking", "5_min": "5-minute prep", "buy_nearby": "Buy nearby", "order": "Order in"}

st.title("My foods & rules")

# --- My Foods ------------------------------------------------------------------------------
st.subheader("My Foods")
st.caption("Foods you can actually get. Suggestions use only the available ones. Nutrition is estimated when logged.")
foods = call(api.my_foods) or []
table = pd.DataFrame(
    [{"name": f["name"], "effort": f["effort"], "slots": f["slots"], "available": f["available"]} for f in foods],
    columns=["name", "effort", "slots", "available"],
)
edited = st.data_editor(
    table,
    key="my_foods_editor",
    num_rows="dynamic",
    hide_index=True,
    column_config={
        "name": st.column_config.TextColumn("Food", required=True),
        "effort": st.column_config.SelectboxColumn(
            "Effort", options=list(EFFORT), format_func=EFFORT.get, default="no_cook"
        ),
        "slots": st.column_config.MultiselectColumn("Good for", options=SLOTS, help="Empty = any meal"),
        "available": st.column_config.CheckboxColumn("Available", default=True),
    },
)
if st.button("Save My Foods", type="primary"):
    rows = []
    for r in edited.to_dict("records"):
        name = str(r.get("name") or "").strip()
        if not name:
            continue
        slots = r.get("slots")
        rows.append(
            {
                "name": name,
                "effort": r.get("effort") or "no_cook",
                "slots": list(slots) if isinstance(slots, (list, tuple)) else [],
                "available": bool(r.get("available")) if pd.notna(r.get("available")) else True,
            }
        )
    if call(api.save_my_foods, rows) is not None:
        st.toast(f"Saved {len(rows)} foods ✅")
        st.rerun()

# --- Rules ----------------------------------------------------------------------------------
st.subheader("Food rules")
st.caption('Write a rule in plain words, e.g. "idli at most 3 days a week" or "no tea after 4 PM".')
with st.form("rule"):
    text = st.text_input("New rule")
    check = st.form_submit_button("Check rule")
if check and text.strip():
    st.session_state["rule_draft"] = call(api.parse_rule, text.strip())

draft = st.session_state.get("rule_draft")
if draft:
    st.info(f"I understood: **{draft['summary']}**")
    ok, cancel = st.columns(2)
    if ok.button("✅ Save this rule", type="primary", width="stretch"):
        if call(api.save_rule, {k: draft[k] for k in ("kind", "food", "limit", "time", "summary", "original_text")}):
            st.session_state.pop("rule_draft", None)
            st.toast("Rule saved")
            st.rerun()
    if cancel.button("Cancel", width="stretch"):
        st.session_state.pop("rule_draft", None)
        st.rerun()

ICON = {"ok": "🟢", "at_limit": "🟡", "broken": "🔴"}
rules = call(api.rules) or []
if not rules:
    st.caption("No rules yet.")
for r in rules:
    cols = st.columns([6, 1])
    cols[0].markdown(f"{ICON.get(r['state'], '⚪')} **{r['summary']}**  \n{r['status']}")
    if cols[1].button("Delete", key=f"rule{r['id']}"):
        call(api.delete_rule, r["id"])
        st.rerun()
