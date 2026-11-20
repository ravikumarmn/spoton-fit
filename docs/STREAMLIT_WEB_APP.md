# Streamlit web app (developer and admin tool)

A small web client in `frontend/`. It is **frozen** as a developer and admin tool; new features go into the Flutter app.

```bash
uv sync --group web
uv run uvicorn spotonfit.api.main:app --reload                 # terminal 1: http://127.0.0.1:8000
uv run --group web streamlit run frontend/app.py               # terminal 2: http://localhost:8501
```

Set `SPOTON_API_URL` if the API runs somewhere other than `http://127.0.0.1:8000`. Sign-in lasts for the browser tab.

1. **Create account**. You land on **Profile**; fill it in once to get your calorie and protein targets.
2. **Log meal**:
   - Choose 📷 Camera, 🖼️ Upload or ⌨️ Type, add a note if you like, then **Analyze**.
   - Review the draft table: fix a **Count** (totals update live), correct a per-unit value, or add or delete rows. Oily and fried items are flagged, and any doubts appear as warnings.
   - Choose the meal, then **Save meal**.
   - Values you correct are **remembered** for that food next time.
3. **Today**:
   - What's left (calories, protein, carbs, fat, water, steps).
   - 💧 +250/+500 ml buttons; steps, weight and workouts.
   - Today's meals with ⭐ favourite, 🔁 log again, 🗑️ delete.
4. **Coach**:
   - Ask *"Can I have tea now?"*. The reply streams in word by word.
   - Today's conversation is kept: it's still there after a refresh or an API restart.
   - **What should I eat next?** gives two options from **My Foods** or **Any food**; **Review & log this** opens one as a draft.
   - Messages about worrying symptoms (chest pain, fainting, …) or disordered eating get a fixed safety reply, not diet advice.
5. **My foods**:
   - List the foods you can actually get (effort: no cooking / 5-minute / buy nearby / order in).
   - Add food rules in plain words ("idli at most 3 days a week", "no tea after 4 PM"). SpotOn shows how it understood each rule; you confirm it. Rules are then checked against what you log: gentle nudges appear on Today, and blocked foods are never suggested.
6. **Progress**:
   - **Weekly review**, ready every Sunday for the week just finished:
     - days logged, average calories and protein days, and the trend change;
     - at most one suggested change, which you **Accept** or **Keep as is**.
   - Weight with its smoothed **trend**, and a 4-week range.
   - **Learned maintenance** with a plain-language explanation of how it was worked out.
   - "85 kg likely between early-Feb and mid-Apr": always a range.
   - Waist, hip and body-fat measurements.
   - Today shows a banner when a review is waiting.
7. **History**: day/week/month/year charts for calories and protein vs target, steps, and weight with its trend.
8. **Profile**: targets, remembered foods (forget any), **export** your data (JSON or CSV), and sign out.

You can also log a favourite or recent meal again from the ⭐ section on **Log meal**. Sign-in lasts for the browser tab: a refresh or new tab asks you to sign in again (see "Known limits").
