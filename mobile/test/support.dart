import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:spoton/core/api/spoton_api.dart';
import 'package:spoton/core/api_error.dart';
import 'package:spoton/core/models.dart';

/// Real API responses captured by scripts/gen_mobile_fixtures.py.
Object? fixture(String name) =>
    jsonDecode(File('test/fixtures/$name.json').readAsStringSync());
Map<String, dynamic> fixtureMap(String name) =>
    (fixture(name) as Map).cast<String, dynamic>();
List<Map<String, dynamic>> fixtureList(String name) => (fixture(name) as List)
    .map((e) => (e as Map).cast<String, dynamic>())
    .toList();

class SavedMeal {
  SavedMeal(
    this.slot,
    this.items,
    this.source,
    this.key,
    this.note,
    this.favourite,
    this.eatenAt,
  );
  final String slot, source, key;
  final List<FoodItem> items;
  final String? note;
  final bool favourite;
  final DateTime? eatenAt;
}

/// An in-memory SpotOnApi seeded with real fixtures. Records what the UI asked for.
class FakeApi implements SpotOnApi {
  FakeApi({this.signedIn = true, this.hasProfile = true});

  bool signedIn, hasProfile;
  final calls = <String>[];
  final saved = <SavedMeal>[];
  ApiException? analyzeError;
  Object? coachError;
  String coachReply = 'Yes, have tea. You have room today.';
  String? coachSafety;
  List<ChatMessage> thread = [];
  String? lastDecision;
  String? lastWorkoutText;
  DateTime? lastWorkoutDay;
  String? lastAnalyzeNote;
  bool lastAnalyzeHadImage = false;
  Profile? savedProfile;

  Draft draft = Draft.fromJson(fixtureMap('draft'));
  late Profile profileData = Profile.fromJson(fixtureMap('profile'));
  Today todayData = Today.fromJson(fixtureMap('today'));
  List<Meal> mealsToday = fixtureList('meals_today')
      .map(Meal.fromJson)
      .toList();
  List<MyFood> foods = fixtureList('my_foods').map(MyFood.fromJson).toList();
  List<FoodRule> ruleList = fixtureList('rules')
      .map(FoodRule.fromJson)
      .toList();
  WeeklyReview weekly = WeeklyReview.fromJson(fixtureMap('weekly_review'));

  @override
  Future<void> ping() async => calls.add('ping');

  @override
  Future<bool> get hasSession async => signedIn;

  @override
  Future<void> register(String email, String password) async {
    calls.add('register:$email');
    signedIn = true;
    hasProfile = false;
  }

  @override
  Future<void> login(String email, String password) async {
    calls.add('login:$email');
    if (password == 'wrong-pass') {
      throw const ApiException(
        status: 401,
        code: 'invalid_credentials',
        message: 'Incorrect email or password',
      );
    }
    signedIn = true;
  }

  @override
  Future<void> logout() async {
    calls.add('logout');
    signedIn = false;
  }

  @override
  Future<void> deleteAccount(String password) async {
    calls.add('deleteAccount');
    if (password != 'right-pass') {
      throw const ApiException(
        status: 401,
        code: 'invalid_credentials',
        message: 'Incorrect password',
      );
    }
    signedIn = false;
  }

  @override
  Future<UserInfo> me() async => UserInfo.fromJson(fixtureMap('me'));

  @override
  Future<Profile?> profile() async =>
      hasProfile ? (savedProfile ?? profileData) : null;

  @override
  Future<Profile> saveProfile(ProfileInput input) async {
    calls.add('saveProfile');
    hasProfile = true;
    savedProfile = Profile(
      input: input,
      targets: profileData.targets,
      warnings: profileData.warnings,
    );
    return savedProfile!;
  }

  @override
  Future<Today> today({DateTime? day}) async => todayData;

  @override
  Future<void> addWater(int ml, {DateTime? day}) async =>
      calls.add('water:$ml${day == null ? '' : '@${_ymd(day)}'}');

  @override
  Future<void> setSteps(DateTime day, int steps) async =>
      calls.add('steps:$steps');

  @override
  Future<void> logWeight(double kg, {DateTime? day}) async =>
      calls.add('weight:$kg${day == null ? '' : '@${_ymd(day)}'}');

  @override
  Future<List<WorkoutResult>> logWorkout(String text, {DateTime? day}) async {
    lastWorkoutText = text;
    lastWorkoutDay = day;
    return fixtureList('workouts').map(WorkoutResult.fromJson).toList();
  }

  @override
  Future<History> history(String period) async =>
      History.fromJson(fixtureMap('history_$period'));

  @override
  Future<Draft> analyze({String? note, UploadImage? image}) async {
    calls.add('analyze');
    lastAnalyzeNote = note;
    lastAnalyzeHadImage = image != null;
    final e = analyzeError;
    if (e != null) throw e;
    return draft;
  }

  @override
  Future<Meal> saveMeal({
    required String slot,
    required List<FoodItem> items,
    required String source,
    required String idempotencyKey,
    String? note,
    bool isFavourite = false,
    DateTime? eatenAt,
  }) async {
    calls.add('saveMeal');
    saved.add(
      SavedMeal(
        slot,
        items.map((i) => i.copy()).toList(),
        source,
        idempotencyKey,
        note,
        isFavourite,
        eatenAt,
      ),
    );
    return Meal.fromJson(fixtureMap('meal'));
  }

  @override
  Future<List<Meal>> meals({DateTime? day}) async => mealsToday;

  @override
  Future<List<Meal>> recentMeals() async =>
      fixtureList('recent_meals').map(Meal.fromJson).toList();

  @override
  Future<List<Meal>> favouriteMeals() async =>
      fixtureList('favourite_meals').map(Meal.fromJson).toList();

  @override
  Future<Meal> setFavourite(String mealId, bool value) async {
    calls.add('favourite:$mealId:$value');
    return mealsToday.first;
  }

  @override
  Future<Meal> updateMeal(
    String mealId, {
    required String slot,
    required List<FoodItem> items,
  }) async {
    calls.add('updateMeal:$mealId');
    saved.add(
      SavedMeal(
        slot,
        items.map((i) => i.copy()).toList(),
        'edit',
        mealId,
        null,
        false,
        null,
      ),
    );
    return mealsToday.first;
  }

  @override
  Future<Meal> repeatMeal(String mealId) async {
    calls.add('repeat:$mealId');
    return mealsToday.first;
  }

  @override
  Future<void> deleteMeal(String mealId) async => calls.add('delete:$mealId');

  @override
  Future<Suggestions> suggestions(String mode) async {
    calls.add('suggestions:$mode');
    return Suggestions.fromJson(fixtureMap('suggestions'));
  }

  @override
  Stream<CoachEvent> coachStream(String message, String threadId) async* {
    calls.add('coach:$message');
    if (coachError != null) throw coachError!;
    yield const CoachStatus('get_today');
    for (final word in coachReply.split(' ')) {
      yield CoachToken('$word ');
    }
    yield CoachDone(coachReply, safety: coachSafety);
  }

  @override
  Future<List<ChatMessage>> coachThread(String threadId) async => thread;

  @override
  Future<List<MyFood>> myFoods() async => foods;

  @override
  Future<List<MyFood>> saveMyFoods(List<MyFood> next) async {
    calls.add('saveMyFoods:${next.length}');
    foods = next;
    return foods;
  }

  @override
  Future<List<FoodRule>> rules() async => ruleList;

  @override
  Future<FoodRule> parseRule(String text) async =>
      FoodRule.fromJson(fixtureMap('rule_parse'));

  @override
  Future<FoodRule> saveRule(FoodRule rule) async {
    calls.add('saveRule');
    return rule;
  }

  @override
  Future<void> deleteRule(String id) async => calls.add('deleteRule');

  @override
  Future<List<RememberedFood>> rememberedFoods() async =>
      fixtureList('food_memory').map(RememberedFood.fromJson).toList();

  @override
  Future<void> forgetFood(String id) async => calls.add('forget');

  @override
  Future<Progress> progress() async =>
      Progress.fromJson(fixtureMap('progress'));

  @override
  Future<WeeklyReview> weeklyReview() async => weekly;

  @override
  Future<void> decideReview(String id, {required bool accept}) async {
    lastDecision = accept ? 'accept' : 'reject';
    calls.add('decide:$lastDecision');
  }

  @override
  Future<void> logMeasurement({
    double? waistCm,
    double? hipCm,
    double? bodyFatPct,
  }) async => calls.add('measurement');

  @override
  Future<Uint8List> export(String format) async {
    calls.add('export:$format');
    return Uint8List.fromList(utf8.encode('{}'));
  }
}

String _ymd(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
