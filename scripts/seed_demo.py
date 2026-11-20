"""Fill a LOCAL SpotOn API with a demo account and four weeks of made-up data.

Used to take the screenshots in docs/screenshots and to try the app with realistic history.
No AI calls are made: meals are saved directly with approximate per-unit values typed in below.
The numbers are illustrative demo data, not nutrition reference values.

    uv run uvicorn spotonfit.api.main:app           # in another terminal
    uv run python scripts/seed_demo.py              # prints the demo login

Options: --url http://127.0.0.1:8000  --email demo@example.com  --password demo-pass-123
         --tz Asia/Kolkata (must match the server's SPOTON_TZ: it decides what "today" is)
Never point this at a server with real users: it creates (or reuses) one account.
"""

import argparse
import datetime as dt
import random
import time
from zoneinfo import ZoneInfo

import httpx

# name, unit, grams_per_unit, kcal, protein, carbs, fat, oil_level  (all per ONE unit; approximate)
FOODS = {
    "egg": ("boiled egg", "piece", 50, 72, 6.3, 0.4, 4.8, "none"),
    "idli": ("idli", "piece", 40, 58, 2.0, 12.0, 0.4, "none"),
    "sambar": ("sambar", "katori", 150, 90, 4.0, 13.0, 2.5, "light"),
    "oats": ("oats with milk", "katori", 200, 190, 8.0, 28.0, 5.0, "none"),
    "banana": ("banana", "piece", 120, 105, 1.3, 27.0, 0.4, "none"),
    "roti": ("roti", "piece", 40, 100, 3.0, 18.0, 2.5, "light"),
    "dal": ("dal", "katori", 150, 150, 8.0, 20.0, 4.0, "light"),
    "rice": ("steamed rice", "katori", 150, 205, 4.0, 45.0, 0.4, "none"),
    "chicken": ("chicken curry", "katori", 180, 230, 24.0, 6.0, 12.0, "medium"),
    "paneer": ("paneer bhurji", "katori", 120, 220, 12.0, 5.0, 16.0, "medium"),
    "curd": ("curd", "katori", 120, 100, 6.0, 8.0, 5.0, "none"),
    "salad": ("cucumber and tomato salad", "bowl", 120, 30, 1.0, 6.0, 0.2, "none"),
    "coffee": ("filter coffee with milk", "cup", 150, 50, 2.0, 5.0, 2.5, "none"),
    "almonds": ("almonds", "handful", 28, 165, 6.0, 6.0, 14.0, "none"),
}

# Each day picks one option per slot: (slot, [(food key, count), ...]). Sized to land near a
# 1,700 kcal target on a typical day.
BREAKFAST = [
    [("egg", 3), ("roti", 2), ("coffee", 1)],
    [("idli", 4), ("sambar", 1), ("egg", 2)],
    [("oats", 1.5), ("banana", 1), ("egg", 2)],
]
LUNCH = [
    [("roti", 3), ("dal", 1.5), ("chicken", 1)],
    [("rice", 1), ("chicken", 1.5), ("curd", 1), ("salad", 1)],
    [("roti", 2), ("paneer", 1.5), ("dal", 1), ("salad", 1)],
]
DINNER = [
    [("roti", 2), ("dal", 1), ("paneer", 1)],
    [("rice", 1), ("chicken", 1.5), ("sambar", 1)],
    [("egg", 3), ("roti", 2), ("curd", 1), ("salad", 1)],
]
SNACK = [[("almonds", 1)], [("banana", 1), ("curd", 1)], [("coffee", 1), ("almonds", 1)]]

TIMES = {"breakfast": "08:30", "lunch": "13:15", "snack": "17:00", "dinner": "20:15"}


class Api:
    def __init__(self, url: str):
        self.c = httpx.Client(base_url=url, timeout=30)
        self.h: dict[str, str] = {}

    def call(self, method: str, path: str, **kw) -> httpx.Response:
        for _ in range(8):
            r = self.c.request(method, path, headers=self.h, **kw)
            if r.status_code != 429:
                return r
            time.sleep(float(r.headers.get("Retry-After", "5")) + 0.5)  # polite: wait out the rate limit
        return r

    def ok(self, method: str, path: str, **kw) -> httpx.Response:
        r = self.call(method, path, **kw)
        if r.status_code >= 400:
            raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        return r


def item(key: str, count: int) -> dict:
    name, unit, grams, kcal, protein, carbs, fat, oil = FOODS[key]
    return {
        "name": name,
        "quantity": count,
        "unit": unit,
        "grams_per_unit": grams,
        "per_unit": {"kcal": kcal, "protein": protein, "carbs": carbs, "fat": fat},
        "oil_level": oil,
        "source": "manual",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--email", default="demo@example.com")
    p.add_argument("--password", default="demo-pass-123")
    p.add_argument("--days", type=int, default=28)
    p.add_argument("--tz", default="Asia/Kolkata", help="the server's SPOTON_TZ")
    a = p.parse_args()
    if not a.url.startswith(("http://127.0.0.1", "http://localhost", "http://10.0.2.2")):
        raise SystemExit("Refusing to seed a non-local server.")

    rng = random.Random(7)  # same demo data every run
    api = Api(a.url)
    creds = {"email": a.email, "password": a.password}
    r = api.call("POST", "/v1/auth/register", json=creds)
    if r.status_code == 409:
        r = api.ok("POST", "/v1/auth/login", json=creds)
    elif r.status_code >= 400:
        raise SystemExit(f"register -> {r.status_code}: {r.text[:300]}")
    api.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    local_now = dt.datetime.now(ZoneInfo(a.tz))
    today = local_now.date()
    start = today - dt.timedelta(days=a.days)
    api.ok(
        "PUT",
        "/v1/profile",
        json={
            "age": 29,
            "sex": "male",
            "height_cm": 174,
            "weight_kg": 84.0,
            "goal": "lose_fat",
            "activity": "light",
            "goal_weight_kg": 76,
            "baseline_steps": 5000,
            "start_date": start.isoformat(),
        },
    )

    for n in range(a.days, -1, -1):
        day = today - dt.timedelta(days=n)
        if day != today and rng.random() < 0.08:
            continue  # an occasional missed day, like real life
        # Weight drifts down about 0.1 kg a day with a little noise; weigh in most mornings.
        kg = 84.0 - 0.09 * (a.days - n) + rng.uniform(-0.35, 0.35)
        if rng.random() < 0.85:
            api.ok("POST", "/v1/weights", json={"kg": round(kg, 1), "day": day.isoformat()})
        slots = {"breakfast": rng.choice(BREAKFAST), "lunch": rng.choice(LUNCH), "dinner": rng.choice(DINNER)}
        if rng.random() < 0.6:
            slots["snack"] = rng.choice(SNACK)
        if day == today:
            # Today is in progress: only meals whose usual time has passed, and no dinner,
            # so there is something left to eat.
            now = local_now.strftime("%H:%M")
            slots = {k: v for k, v in slots.items() if TIMES[k] < now and k not in ("dinner", "snack")}
        for slot, foods in slots.items():
            api.ok(
                "POST",
                "/v1/meals",
                json={
                    "slot": slot,
                    "items": [item(k, c) for k, c in foods],
                    "source": "text",
                    "eaten_at": f"{day.isoformat()}T{TIMES[slot]}:00",
                },
            )
        for _ in range(rng.randint(3, 5)):
            api.ok("POST", "/v1/water", json={"ml": 500, "day": day.isoformat()})
        api.ok("PUT", f"/v1/steps/{day.isoformat()}", json={"steps": rng.randint(3500, 9500)})

    api.ok("POST", "/v1/measurements", json={"waist_cm": 92.0, "body_fat_pct": 24.0})
    print(f"Seeded {a.days + 1} days for {a.email}. Sign in with password: {a.password}")


if __name__ == "__main__":
    main()
