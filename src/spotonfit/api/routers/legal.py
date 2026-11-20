"""Public privacy policy page (store requirement). GET /privacy returns HTML.

The contact line comes from PRIVACY_CONTACT (an email or URL); set it before a store
listing. Keep this text in step with what the code actually stores and sends.
"""

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from spotonfit.config import settings

router = APIRouter(tags=["legal"])

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SpotOn privacy policy</title>
<style>
body{{font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1C2925;background:#F6F7F5;margin:0}}
main{{max-width:720px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:19px;margin:28px 0 6px}}
p,li{{color:#2a3833}} small{{color:#55635E}} a{{color:#2B7A68}}
</style></head><body><main>
<h1>SpotOn privacy policy</h1>
<small>Last updated {updated}</small>

<p>SpotOn is a calorie and coaching app. This page explains what it stores, who processes it and how to delete it.
SpotOn gives estimates, not medical advice. It is for adults (18+).</p>

<h2>What SpotOn stores</h2>
<ul>
<li><b>Account:</b> your email and a hashed password (the password itself is never stored).</li>
<li><b>Profile:</b> age, sex, height, weight, goal, activity level and, if you add them, body fat, goal weight and
body measurements.</li>
<li><b>Logs:</b> meals (foods, amounts, nutrition estimates, your notes), water, steps, weights and workouts.</li>
<li><b>Meal photos:</b> a small thumbnail (at most {thumb} px) of each photo you log. The full photo is used for the
estimate and not stored.</li>
<li><b>Coach:</b> your conversations with the coach, your coach notes, food rules, My Foods and the food values
you corrected (so they are reused).</li>
</ul>

<h2>Who processes it</h2>
<ul>
<li><b>Google Gemini API:</b> meal photos, meal notes, coach messages and the data the coach looks up to
answer (targets, logs, rules and notes) are sent to Google's Gemini models to produce estimates and
replies, under Google's <a href="https://ai.google.dev/gemini-api/terms">Gemini API terms</a>.</li>
<li><b>Google Cloud Run</b> (Singapore) runs the SpotOn server. Its request logs (time, path, status and IP address)
are kept by Google Cloud Logging for a limited period.</li>
<li><b>Neon</b> (Postgres database, AWS Singapore) stores the data listed above.</li>
</ul>
<p>SpotOn does not sell your data, show ads or share it with anyone else.</p>

<h2>Your choices</h2>
<ul>
<li><b>Export:</b> Me &rsaquo; Export my data downloads everything as JSON or CSV.</li>
<li><b>Delete:</b> Me &rsaquo; Delete account permanently deletes your account and everything above, including coach
conversations. It cannot be undone.</li>
<li>You can edit or delete any meal, weight or note at any time.</li>
</ul>

<h2>Security</h2>
<p>Connections use HTTPS. Sign-in uses short-lived tokens; the app keeps them in the phone's secure storage.</p>

<h2>Contact</h2>
<p>{contact}</p>
</main></body></html>
"""


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy() -> HTMLResponse:
    contact = settings.privacy_contact.strip()
    if contact.startswith(("http://", "https://")):
        line = f'Questions or requests: <a href="{escape(contact)}">{escape(contact)}</a>.'
    elif "@" in contact:
        line = f'Questions or requests: <a href="mailto:{escape(contact)}">{escape(contact)}</a>.'
    else:
        line = "Questions or requests: contact the person who invited you to SpotOn."
    return HTMLResponse(
        _PAGE.format(updated=settings.privacy_updated, thumb=settings.thumbnail_side_px, contact=line),
        headers={"Cache-Control": "public, max-age=3600"},
    )
