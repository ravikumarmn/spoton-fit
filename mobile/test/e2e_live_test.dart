// End-to-end against a REAL SpotOn API (the real HttpSpotOnApi, models and server).
// Skipped unless SPOTON_E2E_URL is set, e.g.:
//   SPOTON_E2E_URL=http://127.0.0.1:8790 flutter test test/e2e_live_test.dart
// Add SPOTON_E2E_AI=1 to also call the real model (analyze, coach, rules).
// It creates a throwaway account and deletes it at the end.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:spoton/core/api/http_api.dart';
import 'package:spoton/core/api_error.dart';
import 'package:spoton/core/models.dart';
import 'package:spoton/core/token_store.dart';

void main() {
  final url = Platform.environment['SPOTON_E2E_URL'];
  final withAi = Platform.environment['SPOTON_E2E_AI'] == '1';
  final skip = url == null
      ? 'set SPOTON_E2E_URL to run against a real server'
      : null;

  test(
    'a full day with the real API',
    skip: skip,
    timeout: const Timeout(Duration(minutes: 3)),
    () async {
      final store = MemoryTokenStore();
      final api = HttpSpotOnApi(baseUrl: url ?? '', tokens: store);
      final email = 'e2e-${DateTime.now().microsecondsSinceEpoch}@example.com';
      const password = 'e2e-pass-12345';

      await api.ping();

      // account
      await api.register(email, password);
      expect(await api.hasSession, isTrue);
      expect((await api.me()).email, email);
      expect(await api.profile(), isNull);

      // profile: the gym report's inputs
      final saved = await api.saveProfile(
        ProfileInput(
          age: 26,
          sex: 'male',
          heightCm: 177.8,
          weightKg: 92.2,
          goal: 'lose_fat',
          activity: 'light',
          bodyFatPct: 24,
          goalWeightKg: 85,
        ),
      );
      expect(saved.targets.bmr, 1884);
      expect(saved.warnings, isEmpty);

      var today = await api.today();
      expect(today.leftKcal, today.targets.kcal);

      // quick logs
      await api.addWater(250);
      await api.setSteps(DateTime.now(), 4200);
      await api.logWeight(92.0);

      // a meal, saved twice with the same key: only one meal exists (idempotency)
      final egg = FoodItem(
        name: 'boiled egg',
        quantity: 2,
        unit: 'piece',
        perUnit: const Nutrients(kcal: 72, protein: 6.3, carbs: 0.4, fat: 4.8),
        source: 'manual',
      );
      final first = await api.saveMeal(
        slot: 'breakfast',
        items: [egg],
        source: 'text',
        idempotencyKey: 'e2e-key-1',
      );
      final again = await api.saveMeal(
        slot: 'breakfast',
        items: [egg],
        source: 'text',
        idempotencyKey: 'e2e-key-1',
      );
      expect(again.id, first.id);
      expect(
        first.totals.kcal,
        closeTo(144, 0.01),
      ); // the server's count x per-unit
      today = await api.today();
      expect(today.eaten.kcal, closeTo(144, 0.01));
      expect(today.waterMl, 250);
      expect(today.steps, 4200);
      expect((await api.meals()).single.id, first.id);

      // edit, favourite, repeat, delete
      await api.setFavourite(first.id, true);
      expect((await api.favouriteMeals()).single.id, first.id);
      final updated = await api.updateMeal(
        first.id,
        slot: 'lunch',
        items: [egg..quantity = 3],
      );
      expect(updated.totals.kcal, closeTo(216, 0.01));
      final repeated = await api.repeatMeal(first.id);
      await api.deleteMeal(repeated.id);
      expect(
        await api.rememberedFoods(),
        isNotEmpty,
      ); // 'manual' items are remembered

      // progress, history, review
      final progress = await api.progress();
      expect(progress.maintenance.explanation, isNotEmpty);
      expect((await api.history('week')).points, isNotEmpty);
      expect((await api.weeklyReview()).nextReviewOn.year, greaterThan(2000));
      await api.logMeasurement(waistCm: 98.5);

      // my foods and rules
      await api.saveMyFoods([const MyFood(name: 'Curd', effort: 'buy_nearby')]);
      expect((await api.myFoods()).single.name, 'Curd');

      // the real model
      if (withAi) {
        final draft = await api.analyze(note: '2 boiled eggs and a banana');
        expect(draft.items.length, greaterThanOrEqualTo(2));
        final total = draft.items.fold(0.0, (s, i) => s + i.total.kcal);
        expect(
          total,
          inInclusiveRange(150, 400),
          reason: 'plausible calories for 2 eggs and a banana: $total',
        );
        stdout.writeln(
          'AI estimate: ${draft.items.map((i) => '${i.quantity} x ${i.name} (${i.perUnit.kcal} kcal each)').join(', ')} = ${total.round()} kcal',
        );

        final rule = await api.parseRule('no tea after 4 pm');
        expect(rule.kind, 'not_after');
        expect(rule.time, '16:00');

        final events = await api
            .coachStream('Can I have tea now?', '2026-11-19')
            .toList();
        expect(events.last, isA<CoachDone>());
        expect((events.last as CoachDone).reply, isNotEmpty);
        stdout.writeln('Coach: ${(events.last as CoachDone).reply}');
      }

      // export
      final export = jsonDecode(utf8.decode(await api.export('json'))) as Map;
      expect(export['account'], isNotEmpty);

      // delete the account: needs the password; afterwards nothing remains
      await expectLater(
        api.deleteAccount('wrong-password'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'invalid_credentials',
          ),
        ),
      );
      expect(await api.hasSession, isTrue);
      await api.deleteAccount(password);
      expect(await api.hasSession, isFalse);
      await expectLater(
        api.login(email, password),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'invalid_credentials',
          ),
        ),
      );
    },
  );
}
