"""Food-rule engine (core/rules.py): pure, deterministic."""

import datetime as dt
from zoneinfo import ZoneInfo

from spotonfit.core.rules import Eaten, Rule, blocked_foods, evaluate, matches, nudges, validate

TZ = ZoneInfo("Asia/Kolkata")
THU = dt.datetime(2026, 11, 19, 17, 0, tzinfo=TZ)  # a Thursday, 5 PM


def at(day_offset: int, hour: int, minute: int = 0) -> dt.datetime:
    return (THU + dt.timedelta(days=day_offset)).replace(hour=hour, minute=minute)


def one(rule, eaten, now=THU):
    return evaluate([rule], eaten, now, week_starts_on="monday")[0]


def test_matching_is_word_based():
    assert matches("tea", "masala tea") and matches("idli", "Idlis")
    assert not matches("tea", "steak") and not matches("egg", "eggplant curry")
    assert matches("chicken biryani", "Chicken Biryani (restaurant)")


def test_max_days_per_week_counts_days_not_servings():
    rule = Rule("r", "max_days_per_week", "idli", limit=3)
    used = [Eaten(at(-3, 8), "idli", 3), Eaten(at(-2, 8), "idli", 4), Eaten(at(-1, 8), "idli", 2)]  # Mon, Tue, Wed
    s = one(rule, used)
    assert (s.state, s.used, s.blocks_now) == ("at_limit", 3, True)  # a 4th day would break it
    s = one(rule, [*used[1:], Eaten(at(0, 8), "idli")])  # Tue, Wed, today
    assert (s.state, s.blocks_now) == ("at_limit", False)  # today already counted: more today is fine
    s = one(rule, [*used, Eaten(at(0, 8), "idli")])
    assert s.state == "broken" and "fresh start" in s.message
    last_week = [Eaten(at(-7, 8), "idli")] * 5
    assert one(rule, last_week).state == "ok"  # calendar week: last week doesn't count


def test_max_per_day_sums_quantities():
    rule = Rule("r", "max_per_day", "tea", limit=2)
    assert one(rule, [Eaten(at(0, 9), "masala tea", 1)]).state == "ok"
    s = one(rule, [Eaten(at(0, 9), "tea", 1), Eaten(at(0, 12), "tea", 1)])
    assert (s.state, s.blocks_now) == ("at_limit", True)
    assert one(rule, [Eaten(at(-1, 9), "tea", 5)]).state == "ok"  # yesterday doesn't count


def test_time_rules():
    no_tea_late = Rule("r", "not_after", "tea", time=dt.time(16, 0))
    assert one(no_tea_late, [], now=THU.replace(hour=15)).blocks_now is False
    assert one(no_tea_late, [], now=THU).blocks_now is True
    assert one(no_tea_late, [Eaten(at(0, 16, 30), "tea")]).state == "broken"
    assert one(no_tea_late, [Eaten(at(0, 10), "tea")]).state == "ok"
    no_early_coffee = Rule("r", "not_before", "coffee", time=dt.time(9, 0))
    assert one(no_early_coffee, [Eaten(at(0, 7), "filter coffee")]).state == "broken"


def test_avoid_and_helpers():
    no_sugar = Rule("r", "avoid", "sugar")
    s = one(no_sugar, [Eaten(at(0, 9), "sugar", 2)])
    assert s.state == "broken" and s.blocks_now
    statuses = evaluate([no_sugar, Rule("t", "max_per_day", "tea", limit=3)], [], THU, "monday")
    assert blocked_foods(statuses) == ["sugar"] and nudges(statuses) == []


def test_week_start_follows_the_setting():
    from spotonfit.core.rules import week_start

    assert week_start(THU.date(), "monday") == dt.date(2026, 11, 16)
    assert week_start(THU.date(), "sunday") == dt.date(2026, 11, 15)
    assert week_start(dt.date(2026, 11, 15), "sunday") == dt.date(2026, 11, 15)


def test_validate():
    assert validate("max_per_day", None, None) and validate("not_after", None, None)
    assert validate("not_after", None, "4pm") and validate("not_after", None, "16:00") is None
    assert validate("avoid", None, None) is None
