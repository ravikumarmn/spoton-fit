import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:spoton/app.dart';
import 'package:spoton/core/api/spoton_api.dart';
import 'package:spoton/core/api_error.dart';
import 'package:spoton/core/models.dart';
import 'package:spoton/core/providers.dart';
import 'package:spoton/features/log/log_state.dart';
import 'package:spoton/features/onboarding/onboarding.dart' show explainPlan;
import 'package:spoton/features/me/me_screens.dart';
import 'package:spoton/ui/widgets.dart' show QuantityStepper;
import 'package:spoton/router.dart';

import 'support.dart';

class Harness {
  Harness(this.tester, this.api);
  final WidgetTester tester;
  final FakeApi api;
  final shared = <(String, String)>[];

  Future<void> pump({double textScale = 1.0}) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    tester.view.physicalSize = const Size(
      1080,
      2340,
    ); // 360 x 780 dp: a typical phone
    tester.view.devicePixelRatio = 3.0;
    tester.platformDispatcher.textScaleFactorTestValue = textScale;
    addTearDown(() {
      tester.view.reset();
      tester.platformDispatcher.clearAllTestValues();
    });
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          prefsProvider.overrideWithValue(prefs),
          apiProvider.overrideWithValue(api),
          pickPhotoProvider.overrideWithValue(
            ({required bool camera}) async => UploadImage(
              name: 'meal.jpg',
              bytes: Uint8List.fromList([1, 2, 3]),
            ),
          ),
          shareFileProvider.overrideWithValue(
            (bytes, name, mime) async => shared.add((name, mime)),
          ),
        ],
        child: const SpotOnApp(),
      ),
    );
    await settle();
  }

  Future<void> settle() async {
    for (var i = 0; i < 40; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  /// Scrolls until [base] is built and on screen (lists build rows lazily).
  /// Pass a plain finder: Flutter's scroll helpers cannot evaluate a `.first` finder with no match.
  Future<void> reveal(Finder base) async {
    if (base.evaluate().isNotEmpty) {
      await tester.ensureVisible(base.first);
    } else {
      await tester.scrollUntilVisible(base, 300, scrollable: _scrollable);
    }
  }

  /// The list to scroll: the open bottom sheet's, else the page's. Only vertical lists: the
  /// first Scrollable can be a sideways chip row, which never reveals rows below the fold.
  Finder get _scrollable {
    final vertical = find.byWidgetPredicate(
      (w) =>
          w is Scrollable &&
          axisDirectionToAxis(w.axisDirection) == Axis.vertical,
    );
    final sheet = find.byType(BottomSheet);
    return sheet.evaluate().isNotEmpty
        ? find.descendant(of: sheet, matching: vertical).first
        : vertical.first;
  }

  Future<void> tap(Finder base) async {
    await reveal(base);
    await tester.tap(base.first);
    await settle();
  }

  Future<void> tapText(String text) => tap(find.text(text));

  Future<void> enter(String label, String value) async {
    final f = find.widgetWithText(TextFormField, label);
    await reveal(f);
    await tester.enterText(f.first, value);
    await tester.pump();
  }
}

void main() {
  markdownInChat();
  group('router guards', () {
    test('each sign-in state may only be in its own part of the app', () {
      expect(redirectFor(AuthStatus.checking, '/today'), '/splash');
      expect(redirectFor(AuthStatus.checking, '/splash'), isNull);
      expect(redirectFor(AuthStatus.unreachable, '/today'), '/splash');
      expect(redirectFor(AuthStatus.signedOut, '/today'), '/welcome');
      expect(redirectFor(AuthStatus.signedOut, '/log/review'), '/welcome');
      expect(redirectFor(AuthStatus.signedOut, '/sign-in'), isNull);
      expect(redirectFor(AuthStatus.onboarding, '/today'), '/onboarding/goal');
      expect(redirectFor(AuthStatus.onboarding, '/onboarding/plan'), isNull);
      expect(redirectFor(AuthStatus.ready, '/splash'), '/today');
      expect(redirectFor(AuthStatus.ready, '/welcome'), '/today');
      expect(redirectFor(AuthStatus.ready, '/onboarding/goal'), '/today');
      expect(redirectFor(AuthStatus.ready, '/me/profile'), isNull);
    });
  });

  group('account', () {
    testWidgets(
      'a returning user goes straight to Today (the session persists)',
      (tester) async {
        final h = Harness(tester, FakeApi());
        await h.pump();
        expect(find.text('Calories left'), findsOneWidget);
        expect(find.text('Welcome back'), findsNothing);
      },
    );

    testWidgets('a short password is explained before anything is sent', (
      tester,
    ) async {
      final api = FakeApi(signedIn: false);
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Get started');
      await h.enter('Email', 'admin@gmail.com');
      await h.enter('Password (at least 8 characters)', 'admin');
      await h.tapText('Create account');
      expect(
        find.text('Use at least 8 characters (yours has 5)'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.startsWith('register')), isEmpty);
    });

    testWidgets('wrong password shows the API message', (tester) async {
      final api = FakeApi(signedIn: false);
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('I already have an account');
      await h.enter('Email', 'me@example.com');
      await h.enter('Password', 'wrong-pass');
      await h.tapText('Sign in');
      expect(find.text('Incorrect email or password'), findsOneWidget);
    });

    testWidgets('sign up, then the 3-step onboarding, the plan, then Today', (
      tester,
    ) async {
      final api = FakeApi(signedIn: false);
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Get started');
      await h.enter('Email', 'new@example.com');
      await h.enter('Password (at least 8 characters)', 'long-password-1');
      await h.tapText('Create account');

      expect(find.text("What's your goal?"), findsOneWidget);
      await h.tapText('Build muscle');
      await h.tapText('Continue');
      expect(find.text('About you'), findsOneWidget);
      await h.enter('Age', '26');
      await h.enter('Weight', '92.2');
      await h.tapText('Continue');
      expect(find.text('How active are you?'), findsOneWidget);
      await h.tapText('Moderate');
      await h.tapText('See my plan');

      expect(find.text('Your plan'), findsOneWidget);
      final p = api.savedProfile!.input;
      expect(
        (p.goal, p.age, p.weightKg, p.activity),
        ('build_muscle', 26, 92.2, 'moderate'),
      );
      expect(
        find.text('2,070 kcal'),
        findsOneWidget,
      ); // the server's number, shown as is
      await h.tapText('How this was worked out');
      expect(find.textContaining('At rest your body burns'), findsOneWidget);
      await h.tapText('Start logging');
      expect(find.text('Calories left'), findsOneWidget);
    });

    testWidgets(
      'the plan explanation is computed from the numbers, not assumed',
      (tester) async {
        final lose = Profile.fromJson(fixtureMap('profile'));
        final lines = explainPlanForTest(lose);
        expect(lines.any((l) => l.contains('below maintenance')), isTrue);
        expect(lines.any((l) => RegExp(r'\d+% below').hasMatch(l)), isTrue);
      },
    );

    testWidgets(
      'deleting the account needs the password and ends the session',
      (tester) async {
        final api = FakeApi();
        final h = Harness(tester, api);
        await h.pump();
        await h.tapText('Me');
        await h.tapText('Delete account');
        expect(find.text('Delete my account'), findsOneWidget);
        await tester.enterText(find.byType(TextField), 'wrong-pass');
        await h.tapText('Delete my account');
        await h.tapText('Delete everything');
        expect(find.text('Incorrect password'), findsOneWidget);
        await tester.enterText(find.byType(TextField), 'right-pass');
        await h.tapText('Delete my account');
        await h.tapText('Delete everything');
        expect(find.text('Get started'), findsOneWidget); // back at Welcome
        expect(
          find.textContaining('account and all its data were deleted'),
          findsOneWidget,
        );
      },
    );
  });

  group('Today', () {
    testWidgets('shows what is left, with the equation in words', (
      tester,
    ) async {
      final h = Harness(tester, FakeApi());
      await h.pump();
      expect(find.text('Calories left'), findsOneWidget);
      expect(find.text('840'), findsOneWidget);
      expect(find.text('2,070 target − 1,230 eaten'), findsOneWidget);
      expect(find.text('Protein'), findsOneWidget);
      expect(find.textContaining('62 left'), findsOneWidget);
      await h.reveal(find.text('Meals'));
      expect(find.text('Meals'), findsOneWidget);
      expect(
        find.textContaining('Breakfast ·'),
        findsOneWidget,
      ); // the day's meals are listed below it
    });

    testWidgets('over target is amber wording, never "failed"', (tester) async {
      final api = FakeApi();
      final j = fixtureMap('today');
      (j['left'] as Map)['kcal'] = -120.0;
      api.todayData = Today.fromJson(j);
      final h = Harness(tester, api);
      await h.pump();
      expect(find.text('Calories over'), findsOneWidget);
      expect(find.text('120'), findsOneWidget);
    });

    testWidgets('quick add: +250 ml water in one tap', (tester) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('+250 ml water');
      expect(api.calls, contains('water:250'));
    });

    testWidgets('meal options: log again and favourite', (tester) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tap(find.byTooltip('Meal options'));
      await h.tapText('Log again now');
      expect(api.calls.where((c) => c.startsWith('repeat')), hasLength(1));
      await h.tap(find.byTooltip('Meal options'));
      await h.tapText('Remove from favourites');
      expect(api.calls, contains('favourite:${api.mealsToday.first.id}:false'));
    });

    testWidgets('deleting a meal offers Undo, which saves it again', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tap(find.byTooltip('Meal options'));
      await h.tapText('Delete meal');
      expect(api.calls.where((c) => c.startsWith('delete')), hasLength(1));
      expect(find.text('Meal deleted'), findsOneWidget);
      await h.tapText('Undo');
      expect(api.saved.single.items.first.name, 'boiled egg');
      expect(api.saved.single.slot, 'breakfast');
    });

    testWidgets('a pending weekly review is announced on Today', (
      tester,
    ) async {
      final h = Harness(tester, FakeApi());
      await h.pump();
      expect(find.text('Your weekly review is ready'), findsOneWidget);
      await h.tapText('Your weekly review is ready');
      expect(find.text('Progress'), findsWidgets);
      expect(find.textContaining('Weekly review ·'), findsOneWidget);
    });
  });

  group('logging a meal', () {
    Future<void> toReview(
      Harness h, {
      String text = '6 boiled eggs and 3 puris',
    }) async {
      await h.tap(find.byIcon(Icons.add));
      expect(find.text('Log a meal'), findsOneWidget);
      await h.tapText('Type');
      await h.tester.enterText(
        find.widgetWithText(TextField, 'What did you eat?'),
        text,
      );
      await h.tester.pump();
      await h.tapText('Analyze');
    }

    testWidgets(
      'type it, review, change a count, save: totals are count x per-unit',
      (tester) async {
        final api = FakeApi();
        final h = Harness(tester, api);
        await h.pump();
        await toReview(h);
        expect(find.text('Review meal'), findsOneWidget);
        expect(api.lastAnalyzeNote, '6 boiled eggs and 3 puris');
        expect(api.lastAnalyzeHadImage, isFalse);
        expect(find.text('Total 762 kcal'), findsOneWidget); // 6 x 72 + 3 x 110
        expect(find.textContaining('puri looks oily'), findsOneWidget);
        expect(find.text('Oily'), findsOneWidget);

        await h.tap(
          find.descendant(
            of: find.byType(QuantityStepper).first,
            matching: find.byIcon(Icons.add),
          ),
        );
        expect(
          find.text('Total 834 kcal'),
          findsOneWidget,
        ); // 7 x 72 + 330: updates without a server call
        await h.tapText('Save meal');

        final s = api.saved.single;
        expect(s.slot, 'breakfast');
        expect(s.source, 'text');
        expect(s.key, isNotEmpty);
        expect(s.items.first.quantity, 7);
        expect(
          s.items.first.source,
          'ai_estimate',
        ); // only the count changed: nothing to remember
        expect(find.text('Calories left'), findsOneWidget); // back on Today
      },
    );

    testWidgets('a photo goes through the camera and is analyzed', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tap(find.byIcon(Icons.add));
      await h.tapText('Take photo');
      expect(api.lastAnalyzeHadImage, isTrue);
      expect(find.text('Review meal'), findsOneWidget);
      await h.tapText('Save meal');
      expect(api.saved.single.source, 'photo');
    });

    testWidgets(
      'correcting a value marks the item as edited so SpotOn remembers it',
      (tester) async {
        final api = FakeApi();
        final h = Harness(tester, api);
        await h.pump();
        await toReview(h);
        await h.tap(find.text('boiled egg'));
        await h.enter('Calories', '78');
        await h.tapText('Save changes');
        expect(find.text('Total 798 kcal'), findsOneWidget); // 6 x 78 + 330
        await h.tapText('Save meal');
        final egg = api.saved.single.items.first;
        expect((egg.source, egg.perUnit.kcal), ('edited', 78));
        expect(api.saved.single.items[1].source, 'ai_estimate');
      },
    );

    testWidgets('adding and removing foods', (tester) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await toReview(h);
      await h.tapText('Add food');
      await h.enter('Food', 'Home laddoo');
      await h.enter('Calories', '150');
      await h.tap(
        find.widgetWithText(FilledButton, 'Add food'),
      ); // the sheet's button, not the chip behind it
      expect(find.text('Home laddoo'), findsOneWidget);
      await h.tap(find.text('puri'));
      await h.tapText('Remove this food');
      await h.tapText('Save meal');
      final items = api.saved.single.items;
      expect(items.map((i) => i.name), ['boiled egg', 'Home laddoo']);
      expect(items.last.source, 'manual');
    });

    testWidgets('closing the review asks before throwing the meal away', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await toReview(h);
      await h.tap(find.byTooltip('Close'));
      expect(find.text('Discard this meal?'), findsOneWidget);
      await h.tapText('Keep editing');
      expect(find.text('Review meal'), findsOneWidget);
      await h.tap(find.byTooltip('Close'));
      await h.tapText('Discard');
      expect(find.text('Calories left'), findsOneWidget);
      expect(api.saved, isEmpty);
    });

    testWidgets('when analysis fails, the user can retry or type it instead', (
      tester,
    ) async {
      final api = FakeApi()
        ..analyzeError = const ApiException(
          status: 502,
          code: 'ai_failed',
          message: 'Food analysis failed, try again',
        );
      final h = Harness(tester, api);
      await h.pump();
      await toReview(h);
      expect(find.text('Food analysis failed, try again'), findsOneWidget);
      api.analyzeError = null;
      await h.tapText('Try again');
      expect(find.text('Review meal'), findsOneWidget);
    });

    testWidgets('a favourite or recent meal is logged again in one tap', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tap(find.byIcon(Icons.add));
      await h.tapText('Recent');
      await h.tapText('Log');
      expect(api.calls.where((c) => c.startsWith('repeat')), isNotEmpty);
      expect(find.text('Calories left'), findsOneWidget);
    });

    testWidgets('editing a saved meal saves changes to that meal', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tap(find.byTooltip('Meal options'));
      await h.tapText('Edit meal');
      expect(find.text('Edit meal'), findsOneWidget);
      await h.tapText('Save changes');
      expect(api.calls.any((c) => c.startsWith('updateMeal:')), isTrue);
    });
  });

  group('coach', () {
    testWidgets('the reply streams in and stays in the conversation', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Coach');
      await tester.enterText(
        find.widgetWithText(TextField, 'Ask your coach'),
        'Can I have tea now?',
      );
      await tester.pump();
      await h.tap(find.byTooltip('Send'));
      expect(api.calls, contains('coach:Can I have tea now?'));
      expect(find.text('Can I have tea now?'), findsWidgets);
      expect(find.text('Yes, have tea. You have room today.'), findsOneWidget);
    });

    testWidgets("today's earlier conversation is loaded from the server", (
      tester,
    ) async {
      final api = FakeApi()
        ..thread = [
          const ChatMessage(role: 'user', content: 'Hello'),
          const ChatMessage(role: 'assistant', content: 'Hi! How can I help?'),
        ];
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Coach');
      expect(find.text('Hi! How can I help?'), findsOneWidget);
    });

    testWidgets('a safety reply is shown in its own calm style', (
      tester,
    ) async {
      final api = FakeApi()
        ..coachReply = 'Please get medical help first.'
        ..coachSafety = 'red_flag';
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Coach');
      await tester.enterText(
        find.widgetWithText(TextField, 'Ask your coach'),
        'I fainted',
      );
      await tester.pump();
      await h.tap(find.byTooltip('Send'));
      expect(find.text('Please read this'), findsOneWidget);
      expect(find.text('Please get medical help first.'), findsOneWidget);
    });

    testWidgets(
      'a failure is explained and the empty reply bubble disappears',
      (tester) async {
        final api = FakeApi()
          ..coachError = const ApiException(
            status: 503,
            code: 'ai_not_configured',
            message: 'AI is not configured',
          );
        final h = Harness(tester, api);
        await h.pump();
        await h.tapText('Coach');
        await tester.enterText(
          find.widgetWithText(TextField, 'Ask your coach'),
          'hello',
        );
        await tester.pump();
        await h.tap(find.byTooltip('Send'));
        expect(find.text('AI is not configured'), findsOneWidget);
      },
    );

    testWidgets(
      '"What should I eat next?" suggests two options that open in review',
      (tester) async {
        final api = FakeApi();
        final h = Harness(tester, api);
        await h.pump();
        await h.tapText('Coach');
        await h.tapText('What should I eat next?');
        await h.tapText('Suggest two options');
        expect(api.calls, contains('suggestions:my_foods'));
        expect(find.text('Two boiled eggs'), findsOneWidget);
        expect(find.textContaining('156 kcal'), findsWidgets);
        await h.tapText('Review & log this');
        expect(find.text('Review meal'), findsOneWidget);
        expect(find.text('boiled egg'), findsOneWidget);
      },
    );
  });

  group('progress', () {
    testWidgets('accepting the weekly proposal tells the server', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Progress');
      expect(find.textContaining('Suggested: Add 1,500 steps'), findsOneWidget);
      await h.tapText('Accept');
      expect(api.lastDecision, 'accept');
    });

    testWidgets(
      'shows the trend, the prediction as a range, and how maintenance was learned',
      (tester) async {
        final h = Harness(tester, FakeApi());
        await h.pump();
        await h.tapText('Progress');
        expect(find.text('Trend weight'), findsOneWidget);
        expect(find.textContaining('A range, not a promise'), findsOneWidget);
        await h.tap(find.text('Maintenance'));
        expect(find.textContaining('kcal a day on average'), findsOneWidget);
      },
    );

    testWidgets('history shows charts for each period', (tester) async {
      final h = Harness(tester, FakeApi());
      await h.pump();
      await h.tapText('Progress');
      await h.tapText('History');
      expect(find.text('Calories'), findsOneWidget);
      await h.tapText('Week');
      expect(find.text('Protein'), findsOneWidget);
    });
  });

  group('Me', () {
    testWidgets('profile edit saves the changes', (tester) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Me');
      await h.tapText('Edit profile');
      await h.enter('Weight', '90');
      await h.tapText('Save');
      expect(api.savedProfile!.input.weightKg, 90);
      expect(find.text('Profile saved'), findsOneWidget); // toast
      // and the confirmation banner is scrolled into view at the top of the form
      expect(find.textContaining('Saved. Your target is now'), findsOneWidget);
    });

    testWidgets('my foods: add a food', (tester) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Me');
      await h.tapText('My foods');
      await h.tapText('Add food');
      await tester.enterText(find.widgetWithText(TextField, 'Food'), 'Curd');
      await h.tapText('Buy nearby');
      await h.tapText('Save');
      expect(api.foods.map((f) => f.name), contains('Curd'));
      expect(api.foods.last.effort, 'buy_nearby');
    });

    testWidgets('a rule is shown back for confirmation before it is saved', (
      tester,
    ) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Me');
      await h.tapText('Food rules');
      await h.tapText('Add rule');
      await tester.enterText(
        find.widgetWithText(TextField, 'Your rule'),
        'no tea after 4 pm',
      );
      await h.tapText('Check rule');
      expect(
        find.textContaining('I understood: No tea after 4 PM.'),
        findsOneWidget,
      );
      expect(api.calls, isNot(contains('saveRule')));
      await h.tapText('Save this rule');
      expect(api.calls, contains('saveRule'));
    });

    testWidgets('export hands the file to the share sheet', (tester) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Me');
      await h.tapText('Export my data');
      await h.tapText('Export as JSON');
      expect(api.calls, contains('export:json'));
      expect(h.shared.single.$2, 'application/json');
      expect(h.shared.single.$1, endsWith('.json'));
    });

    testWidgets('signing out returns to Welcome', (tester) async {
      final api = FakeApi();
      final h = Harness(tester, api);
      await h.pump();
      await h.tapText('Me');
      await h.tap(find.widgetWithText(OutlinedButton, 'Sign out'));
      await h.tap(find.widgetWithText(TextButton, 'Sign out'));
      expect(api.calls, contains('logout'));
      expect(find.text('Get started'), findsOneWidget);
    });
  });

  group('accessibility', () {
    testWidgets('Today meets tap-target, label and contrast guidelines', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      final h = Harness(tester, FakeApi());
      await h.pump();
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      await expectLater(tester, meetsGuideline(textContrastGuideline));
      handle.dispose();
    });

    testWidgets('Review meets tap-target and label guidelines', (tester) async {
      final handle = tester.ensureSemantics();
      final h = Harness(tester, FakeApi());
      await h.pump();
      await h.tap(find.byIcon(Icons.add));
      await h.tapText('Type');
      await tester.enterText(
        find.widgetWithText(TextField, 'What did you eat?'),
        '6 eggs',
      );
      await tester.pump();
      await h.tapText('Analyze');
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });

    testWidgets('Welcome and sign-in meet the guidelines', (tester) async {
      final handle = tester.ensureSemantics();
      final h = Harness(tester, FakeApi(signedIn: false));
      await h.pump();
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });

    for (final scale in [1.5, 2.0]) {
      testWidgets('nothing overflows at ${(scale * 100).round()}% text size', (
        tester,
      ) async {
        final api = FakeApi();
        final h = Harness(tester, api);
        await h.pump(textScale: scale);
        expect(tester.takeException(), isNull); // Today
        await h.tapText('Progress');
        expect(tester.takeException(), isNull);
        await h.tapText('Coach');
        expect(tester.takeException(), isNull);
        await h.tapText('Me');
        expect(tester.takeException(), isNull);
        await h.tap(find.byIcon(Icons.add));
        expect(tester.takeException(), isNull); // Capture (photo)
        await h.tapText('Type');
        await tester.enterText(
          find.widgetWithText(TextField, 'What did you eat?'),
          '6 eggs',
        );
        await tester.pump();
        await h.tapText('Analyze');
        expect(find.text('Review meal'), findsOneWidget);
        expect(tester.takeException(), isNull); // Review
      });
    }
  });
}

/// The same text the plan screen builds, without pumping the screen.
List<String> explainPlanForTest(Profile p) => explainPlan(p.targets, p.input);

// A coach reply written in Markdown shows as formatted text, never as literal asterisks.
void markdownInChat() {
  testWidgets('coach replies render bold text without asterisks', (
    tester,
  ) async {
    final api = FakeApi()..coachReply = 'You have **1,854 kcal** left.';
    final h = Harness(tester, api);
    await h.pump();
    await h.tapText('Coach');
    await tester.enterText(
      find.widgetWithText(TextField, 'Ask your coach'),
      'tea?',
    );
    await tester.pump();
    await h.tap(find.byTooltip('Send'));
    expect(find.textContaining('**', findRichText: true), findsNothing);
    expect(
      find.text('You have 1,854 kcal left.', findRichText: true),
      findsOneWidget,
    );
  });
}
