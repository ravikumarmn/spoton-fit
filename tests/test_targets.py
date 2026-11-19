from spotonfit.config import EnergyPolicy, TargetPolicy
from spotonfit.core.targets import Goal, Profile, compute_targets, steps_kcal, workout_kcal

ME = Profile(age=26, sex="male", height_cm=177.8, weight_kg=92.2, goal=Goal.LOSE_FAT, body_fat_pct=24.0)


def test_matches_inbody_numbers():
    t = compute_targets(ME)
    assert t.bmi == 29.2
    assert t.bmr == 1884  # InBody printout (PRD T-02)
    assert 1800 <= t.kcal <= 2000
    assert t.kcal >= t.kcal_floor
    assert 150 <= t.protein_g <= 160


def test_trains_four_days_a_week():
    t = compute_targets(Profile(**{**ME.__dict__, "activity": "light"}))
    assert 2000 <= t.kcal <= 2100


def test_protein_uses_reference_weight_for_high_body_fat():
    heavy = Profile(age=30, sex="male", height_cm=175, weight_kg=120, body_fat_pct=35)
    t = compute_targets(heavy)
    assert t.protein_g < 1.7 * 120  # not based on full body weight


def test_floor_never_breached_for_any_goal():
    small = Profile(age=40, sex="female", height_cm=150, weight_kg=48)
    for goal in Goal:
        t = compute_targets(Profile(**{**small.__dict__, "goal": goal}))
        assert t.kcal >= t.kcal_floor >= 1200


def test_step_ramp_caps():
    assert compute_targets(ME, week_index=0).steps == 5500
    assert compute_targets(ME, week_index=30).steps == 10_000


def test_learned_tdee_overrides_formula():
    assert compute_targets(ME, learned_tdee=2600).maintenance == 2600


def test_policy_values_come_from_config_not_code():
    """Tuning lives in config: a different policy changes the targets."""
    gentle = TargetPolicy(
        deficit_fraction=0.10, protein_g_per_kg={"lose_fat": 2.0, "build_muscle": 2.0, "maintain": 1.6}
    )
    default, custom = compute_targets(ME), compute_targets(ME, policy=gentle)
    assert custom.kcal > default.kcal and custom.protein_g > default.protein_g


def test_energy_helpers():
    assert round(workout_kcal(met=7.0, minutes=15, weight_kg=92.2)) == 161  # MET equation
    assert 300 < steps_kcal(10_000, 92.2) < 400
    assert steps_kcal(10_000, 92.2, EnergyPolicy(steps_per_km=2000)) < steps_kcal(10_000, 92.2)
