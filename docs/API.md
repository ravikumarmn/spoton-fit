# API reference

The API is versioned under `/v1`. Interactive docs (Swagger UI) are served at `/docs` and the OpenAPI schema at
`/openapi.json` while the server is running.

All errors use one envelope: `{"error": {"code", "message", "request_id"}}`. Every response carries an `X-Request-ID` header.

| Area | Endpoints |
| --- | --- |
| Ops (public) | `GET /healthz` · `GET /readyz` · `GET /privacy` (privacy policy page; contact from `PRIVACY_CONTACT`) |
| Auth | `POST /v1/auth/register` · `/login` (JSON) · `/token` (form, Swagger) · `/refresh` · `/logout` · `GET /v1/me` · `POST /v1/account/password` · `DELETE /v1/account` |
| Profile | `GET/PUT /v1/profile` · `GET /v1/targets` |
| Meals | `POST /v1/meals/analyze` · `POST /v1/meals` (`Idempotency-Key` header) · `GET /v1/meals?date=` · `GET /v1/meals/recent` · `GET /v1/meals/favourites` · `GET/PATCH/DELETE /v1/meals/{id}` · `POST /v1/meals/{id}/repeat` · `POST /v1/meals/{id}/photo` |
| Food memory | `GET /v1/food-memory` · `DELETE /v1/food-memory/{id}` (your corrected per-unit values, reused next time) |
| Data | `GET /v1/export?format=json\|csv` (everything you logged; CSV comes as a ZIP) |
| Tracking | `POST /v1/water` · `PUT /v1/steps/{date}` · `POST /v1/weights` · `POST /v1/workouts` (water, weights and workouts take an optional `day`; future days are refused) · `GET /v1/today?date=` (with the day's meals and, for today, the weekly review) · `GET /v1/history?period=&from=&to=` |
| My Foods & rules | `GET/PUT /v1/my-foods` · `POST /v1/rules/parse` (plain English → rule, not saved) · `POST /v1/rules` · `GET /v1/rules` (with today's status) · `DELETE /v1/rules/{id}` |
| Progress | `GET /v1/progress` · `GET /v1/reviews/weekly` · `GET /v1/reviews` · `POST /v1/reviews/{id}/decision` (`accept`\|`reject`) · `POST/GET /v1/measurements` |
| AI | `GET /v1/suggestions?mode=my_foods\|ideal` · `POST /v1/coach/messages` (JSON, or SSE with `Accept: text/event-stream`) · `GET /v1/coach/threads/{date}` · `GET/PUT /v1/coach/notes` (remembered across days) |

Coach streaming uses Server-Sent Events: send `Accept: text/event-stream` to `POST /v1/coach/messages`. The server
sends `event: status` (the coach is checking something, such as `get_today`), then `event: token` chunks, then
`event: done` with the full reply. Errors arrive as `event: error`. See [ARCHITECTURE.md](ARCHITECTURE.md) for how the
numbers behind these endpoints are made.

## Try it in the browser (Swagger UI at `/docs`)

1. **`POST /v1/auth/register`**: `{"email": "me@example.com", "password": "at-least-8-chars"}` returns tokens.
2. Click **Authorize** (top right) and enter the email as *username* plus the password. Swagger calls `POST /v1/auth/token` and sends the access token on every request. Access tokens last 15 minutes; click Authorize again when one expires.
3. **`PUT /v1/profile`**: for example `{"age": 26, "sex": "male", "height_cm": 177.8, "weight_kg": 92.2, "goal": "lose_fat", "activity": "light", "body_fat_pct": 24}`. The response includes your targets.
4. **`POST /v1/meals/analyze`**: a `note` ("6 boiled eggs and 3 puris") and/or a photo. You get a **draft** and nothing is saved yet. Each item shows `quantity`, `per_unit`, totals, `oil_level` and a `remark`; the draft also lists `oily_items` and `warnings`.
5. **`POST /v1/meals`**: send `slot` (the draft's `meal_slot`) and the `items`, after changing any `quantity` if needed. The server recomputes totals as quantity × per_unit.
6. **`GET /v1/today`**, **`GET /v1/suggestions`** (two meal ideas that fit what's left), **`POST /v1/coach/messages`** (`{"message": "Can I have tea now?"}`).
7. **`POST /v1/water`**, **`PUT /v1/steps/{date}`**, **`POST /v1/weights`**, **`POST /v1/workouts`** (`{"text": "15 min cycling, 40 min weights"}`), then **`GET /v1/history?period=week`**.

## The same thing from Python

```python
import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000")
t = c.post("/v1/auth/register", json={"email": "me@example.com", "password": "demo-pass-123"}).json()
h = {"Authorization": f"Bearer {t['access_token']}"}
c.put(
    "/v1/profile",
    headers=h,
    json={
        "age": 26,
        "sex": "male",
        "height_cm": 177.8,
        "weight_kg": 92.2,
        "goal": "lose_fat",
        "activity": "light",
        "body_fat_pct": 24,
    },
)
draft = c.post("/v1/meals/analyze", headers=h, data={"note": "6 boiled eggs"}, timeout=30).json()
# with a photo: files={"image": open("meal.jpg", "rb")}
c.post("/v1/meals", headers=h, json={"slot": draft["meal_slot"], "items": draft["items"]})
print(c.get("/v1/today", headers=h).json()["left"])
```
