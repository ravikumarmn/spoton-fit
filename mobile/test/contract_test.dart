// The app's models against REAL API responses (scripts/gen_mobile_fixtures.py).
// If the API changes a response shape, regenerate the fixtures and this test shows what broke.
import 'package:flutter_test/flutter_test.dart';
import 'package:spoton/core/models.dart';

import 'support.dart';

void main() {
  test(
    'draft: client arithmetic (count x per-unit) equals the server totals',
    () {
      final json = fixtureMap('draft');
      final draft = Draft.fromJson(json);
      final server = Nutrients.fromJson((json['totals'] as Map).cast());
      final mine = draft.items.fold(const Nutrients(), (s, i) => s + i.total);
      expect(mine.kcal, closeTo(server.kcal, 0.01));
      expect(mine.protein, closeTo(server.protein, 0.01));
      expect(draft.items.first.name, 'boiled egg');
      expect(draft.items.first.quantity, 6);
      expect(draft.items.first.perUnit.kcal, 72);
      expect(draft.items[1].isOily, isTrue);
      expect(draft.oilyItems, ['puri']);
      expect(draft.items[1].remark, 'deep-fried, very oily');
      expect(draft.mealSlot, 'breakfast');
    },
  );

  test(
    'every saved item round-trips through the save payload the API accepts',
    () {
      final item = FoodItem.fromJson(
        fixtureMap('draft')['items'][0] as Map<String, dynamic>,
      );
      final body = item.toSaveJson();
      expect(body.keys.toSet(), {
        'name',
        'quantity',
        'unit',
        'grams_per_unit',
        'per_unit',
        'oil_level',
        'source',
      });
      expect((body['per_unit'] as Map).keys.toSet(), {
        'kcal',
        'protein',
        'carbs',
        'fat',
        'fibre',
      });
    },
  );

  test('saved meal: items, totals and favourite', () {
    final m = Meal.fromJson(fixtureMap('meal'));
    expect(m.isFavourite, isTrue);
    expect(m.items, hasLength(2));
    expect(m.totals.kcal, closeTo(762, 0.01));
    expect(m.items.first.perUnit.kcal, 72); // the API's computed per_unit
    expect(m.summary, 'boiled egg, puri');
    expect(m.eatenAt.isUtc, isTrue);
  });

  test('today', () {
    final raw = fixtureMap('today');
    final t = Today.fromJson(raw);
    // Targets can include learned maintenance, which depends on the weekday the fixtures were
    // generated; check the parse and the arithmetic rather than one fixed number.
    expect(t.targets.kcal, (raw['targets'] as Map)['kcal']);
    expect(t.targets.kcalFloor, 1880);
    expect(t.eaten.protein, closeTo(81.6, 0.01));
    expect(t.leftKcal, closeTo(t.targets.kcal - t.eaten.kcal, 0.5));
    expect(t.meals, hasLength(2)); // sent with Today (one call)
    expect(t.weeklyReview, isNotNull);
    expect(t.leftProteinG, 62);
    expect(t.waterMl, 500);
    expect(t.steps, 3900);
    expect(t.targets.maintenanceSource, anyOf('formula', 'learned'));
  });

  test('profile and warnings', () {
    final p = Profile.fromJson(fixtureMap('profile'));
    expect(p.input.goal, 'lose_fat');
    expect(p.input.goalWeightKg, 85);
    expect(p.warnings, isEmpty);
    final low = Profile.fromJson(fixtureMap('profile_with_warning'));
    expect(low.warnings.single, contains('unusually low'));
    expect(low.targets.bmr, greaterThan(p.targets.bmr));
  });

  test('history parses day, week and month rows', () {
    for (final period in ['day', 'week', 'month']) {
      final h = History.fromJson(fixtureMap('history_$period'));
      expect(h.period, period);
      expect(h.points, isNotEmpty, reason: period);
      expect(h.points.first.date.year, greaterThan(2000));
    }
    final days = History.fromJson(fixtureMap('history_day'));
    expect(days.points.where((p) => p.kcal > 0), isNotEmpty);
    expect(days.points.any((p) => p.weightKg == 92.0), isTrue);
  });

  test('progress: weight series, learned maintenance and predictions', () {
    final p = Progress.fromJson(fixtureMap('progress'));
    expect(p.trendKg, 92.0);
    expect(p.series.length, greaterThan(20));
    expect(p.maintenance.active, isTrue);
    expect(p.maintenance.explanation, contains('kcal a day on average'));
    expect(p.predictionMessage, contains('A range, not a promise'));
    expect(p.rangeLowKg, lessThan(p.rangeHighKg!));
    expect(p.measurements.single.waistCm, 98.5);
  });

  test('weekly review with a pending proposal', () {
    final w = WeeklyReview.fromJson(fixtureMap('weekly_review'));
    final r = w.review!;
    expect(w.pendingDecision, isTrue);
    expect(r.proposal!.kind, 'steps');
    expect(r.proposal!.delta, 1500);
    expect(r.daysLogged, 7);
    expect(r.weekEnd.difference(r.weekStart).inDays, 6);
    expect(r.decision, isNull);
  });

  test('suggestions', () {
    final s = Suggestions.fromJson(fixtureMap('suggestions'));
    expect(s.mode, 'my_foods');
    expect(s.options, hasLength(2));
    expect(s.options.first.title, 'Two boiled eggs');
    expect(s.options.first.fits, isTrue);
    // 2 eggs x 78 kcal: the fixture user's remembered value replaces the model's 72.
    expect(s.options.first.totals.kcal, 156);
    expect(s.options.first.items.first.source, 'memory');
  });

  test('rules, my foods, remembered foods, measurements, workouts, user', () {
    final rule = FoodRule.fromJson(fixtureMap('rule_parse'));
    expect(rule.kind, 'not_after');
    expect(rule.time, '16:00');
    expect(rule.id, isNull);
    expect(
      rule.toJson().keys,
      containsAll([
        'kind',
        'food',
        'limit',
        'time',
        'summary',
        'original_text',
      ]),
    );
    final stored = fixtureList('rules').map(FoodRule.fromJson).single;
    expect(stored.id, isNotNull);
    expect(stored.state, isNotNull);
    final food = fixtureList('my_foods').map(MyFood.fromJson).single;
    expect(food.effort, '5_min');
    expect(food.slots, ['breakfast']);
    expect(food.toJson().keys.toSet(), {
      'name',
      'effort',
      'slots',
      'available',
    });
    final remembered = fixtureList('food_memory')
        .map(RememberedFood.fromJson)
        .single;
    expect(remembered.kcal, 78);
    expect(
      fixtureList('measurements').map(Measurement.fromJson).single.bodyFatPct,
      24,
    );
    final workouts = fixtureList('workouts')
        .map(WorkoutResult.fromJson)
        .toList();
    expect(workouts.map((w) => w.activity), ['cycling', 'treadmill walk']);
    expect(workouts.first.minutes, 15);
    expect(workouts.first.kcal, greaterThan(100));
    expect(UserInfo.fromJson(fixtureMap('me')).timezone, 'Asia/Kolkata');
  });

  test('profile input serialises to the keys the API expects', () {
    final json = ProfileInput(goalWeightKg: 85).toJson();
    expect(json.keys.toSet(), {
      'age',
      'sex',
      'height_cm',
      'weight_kg',
      'goal',
      'activity',
      'body_fat_pct',
      'goal_weight_kg',
      'baseline_steps',
    });
  });
}
