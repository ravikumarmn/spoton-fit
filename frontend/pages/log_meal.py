"""Log a meal (PRD T-03..T-08): camera / upload / text -> draft -> review & edit -> save.

Editing rules (mirrors the API):
- Change **count** freely: totals are count x per-unit values.
- Change a **per-unit** value or the name: the item becomes "edited" and SpotOn remembers
  your values for that food next time.
- Add a row: a "manual" item (also remembered). Delete a row: it isn't saved.
"""

import pandas as pd
import streamlit as st

from client import get_client
from components import (
    NUTRIENTS,
    OIL_LEVELS,
    SLOTS,
    call,
    clear_draft,
    item_line,
    macro_metrics,
    start_draft,
    totals_from_rows,
)

api = get_client()
PER_UNIT = [f"{k}_per_unit" for k in NUTRIENTS]
COLUMNS = ["name", "quantity", "unit", *PER_UNIT, "oil_level", "remark"]


def _clean(v, default=None):
    return default if v is None or (isinstance(v, float) and pd.isna(v)) else v


def to_items(edited: pd.DataFrame, original: list[dict]) -> list[dict]:
    """Edited table -> API items, deciding each item's source."""
    items = []
    for idx, row in edited.iterrows():
        name = str(_clean(row["name"], "")).strip()
        qty = float(_clean(row["quantity"], 0) or 0)
        if not name or qty <= 0:
            continue
        per_unit = {k: float(_clean(row[f"{k}_per_unit"], 0) or 0) for k in NUTRIENTS}
        orig = original[idx] if isinstance(idx, int) and idx < len(original) else None
        if orig is None:
            source = "manual"
        elif name != orig["name"] or any(abs(per_unit[k] - orig[f"{k}_per_unit"]) > 1e-6 for k in NUTRIENTS):
            source = "edited"
        else:
            source = orig["source"]
        items.append(
            {
                "name": name,
                "quantity": qty,
                "unit": str(_clean(row["unit"], "serving")) or "serving",
                "grams_per_unit": orig.get("grams_per_unit") if orig else None,
                "per_unit": per_unit,
                "oil_level": _clean(row["oil_level"], "none") or "none",
                "remark": _clean(row["remark"], None) or None,
                "source": source,
            }
        )
    return items


st.title("Log a meal")

# --- 1. Input ------------------------------------------------------------------------
if "draft" not in st.session_state:
    mode = st.segmented_control("How?", ["📷 Camera", "🖼️ Upload", "⌨️ Type"], default="📷 Camera")
    photo = None
    if mode == "📷 Camera":
        photo = st.camera_input("Take a photo of your meal")
    elif mode == "🖼️ Upload":
        photo = st.file_uploader("Upload a meal photo", type=["jpg", "jpeg", "png", "webp", "heic", "heif"])
    label = "What did you eat?" if mode == "⌨️ Type" else "Add a note (optional), e.g. 'ate only 2 idlis'"
    note = st.text_area(label, placeholder="6 boiled eggs and 2 chapatis with dal", height=80)

    if st.button("Analyze", type="primary", width="stretch", disabled=not (photo or note.strip())):
        image = (photo.name or "meal.jpg", photo.getvalue(), photo.type or "image/jpeg") if photo else None
        with st.spinner("Looking at your meal…"):
            draft = call(api.analyze, note.strip() or None, image)
        if draft:
            start_draft(draft, "photo" if photo else "text")
            st.rerun()

    with st.expander("⭐ Log a favourite or recent meal again"):
        favourites = call(api.favourite_meals) or []
        recent = [m for m in call(api.recent_meals) or [] if not m["is_favourite"]]
        if not favourites and not recent:
            st.caption("Meals you log (and ⭐ on the Today page) show up here for one-tap repeat.")
        for m in favourites + recent:
            cols = st.columns([5, 1])
            star = "⭐ " if m["is_favourite"] else ""
            names = ", ".join(i["name"] for i in m["items"])
            cols[0].markdown(f"{star}**{m['slot'].title()}**: {names} · {m['totals']['kcal']:.0f} kcal")
            if cols[1].button("Log", key=f"again{m['id']}"):
                if call(api.repeat_meal, m["id"]):
                    st.toast("Logged again ✅")
                    st.switch_page("pages/today.py")
    st.stop()

# --- 2. Review -----------------------------------------------------------------------
draft = st.session_state["draft"]
original = st.session_state["draft_rows"]

if draft.get("clarify"):
    st.info(f"🤔 {draft['clarify']}")
for w in draft.get("warnings", []):
    st.warning(w)
if draft.get("oily_items"):
    st.badge(f"Oily / fried: {', '.join(draft['oily_items'])}", icon="🛢️", color="orange")

st.caption("Check the counts and values. Totals = count × per-unit values. Add or delete rows as needed.")
edited = st.data_editor(
    pd.DataFrame(original, columns=[*COLUMNS, "source", "grams_per_unit"]),
    key=f"editor_{st.session_state['draft_key']}",
    num_rows="dynamic",
    hide_index=True,
    column_order=COLUMNS,
    column_config={
        "name": st.column_config.TextColumn("Food", required=True),
        "quantity": st.column_config.NumberColumn("Count", min_value=0.0, step=0.5, required=True),
        "unit": st.column_config.TextColumn("Unit"),
        "kcal_per_unit": st.column_config.NumberColumn("kcal / unit", min_value=0.0, format="%.0f"),
        "protein_per_unit": st.column_config.NumberColumn("Protein g / unit", min_value=0.0, format="%.1f"),
        "carbs_per_unit": st.column_config.NumberColumn("Carbs g / unit", min_value=0.0, format="%.1f"),
        "fat_per_unit": st.column_config.NumberColumn("Fat g / unit", min_value=0.0, format="%.1f"),
        "fibre_per_unit": st.column_config.NumberColumn("Fibre g / unit", min_value=0.0, format="%.1f"),
        "oil_level": st.column_config.SelectboxColumn("Oil", options=OIL_LEVELS),
        "remark": st.column_config.TextColumn("Note", disabled=True),
    },
)
items = to_items(edited, original)
macro_metrics(totals_from_rows([{**i, **{f"{k}_per_unit": i["per_unit"][k] for k in NUTRIENTS}} for i in items]))

with st.form("save"):
    default_slot = draft.get("meal_slot") if draft.get("meal_slot") in SLOTS else SLOTS[0]
    slot = st.selectbox(
        "Meal", SLOTS, index=SLOTS.index(default_slot), format_func=lambda s: s.replace("_", " ").title()
    )
    favourite = st.checkbox("⭐ Save as favourite (for one-tap repeat)")
    save, discard = st.columns(2)
    do_save = save.form_submit_button("Save meal", type="primary", width="stretch", disabled=not items)
    do_discard = discard.form_submit_button("Discard", width="stretch")

if do_discard:
    clear_draft()
    st.rerun()
if do_save:
    body = {"slot": slot, "items": items, "source": st.session_state["draft_source"], "is_favourite": favourite}
    meal = call(api.save_meal, body, st.session_state["draft_key"])
    if meal:
        clear_draft()
        st.toast(f"Saved: {meal['totals']['kcal']:.0f} kcal ✅")
        remembered = [i["name"] for i in items if i["source"] in ("edited", "manual")]
        if remembered:
            st.toast(f"Remembered your values for: {', '.join(remembered)}")
        st.switch_page("pages/today.py")

with st.expander("What will be saved"):
    for i in items:
        totals = {k: i["quantity"] * i["per_unit"][k] for k in NUTRIENTS}
        st.markdown(f"- {item_line({**i, **totals})} · _{i['source'].replace('_', ' ')}_")
