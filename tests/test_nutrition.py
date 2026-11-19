from spotonfit.core.nutrition import Nutrients, energy_mismatch, item_totals, macro_energy, meal_totals

EGG = Nutrients(kcal=72, protein=6.3, carbs=0.4, fat=4.8)


def test_count_multiplies_per_unit_values():
    six = item_totals(EGG, 6)
    assert six.kcal == 432 and six.protein == 37.8
    assert item_totals(EGG, 4).kcal == 288  # editing the count re-scales, no model call


def test_meal_totals_add_items():
    total = meal_totals([item_totals(EGG, 2), Nutrients(kcal=105, protein=1.3, carbs=27, fat=0.4)])
    assert total.kcal == 249 and total.carbs == 27.8


def test_energy_consistency_check():
    assert round(macro_energy(EGG)) == 70
    assert energy_mismatch(EGG) < 0.05
    nonsense = Nutrients(kcal=500, protein=1, carbs=1, fat=1)  # calories don't match macros
    assert energy_mismatch(nonsense) > 0.9
    assert energy_mismatch(Nutrients()) == 0
