import 'dart:typed_data';

import '../models.dart';

/// A photo to analyze.
class UploadImage {
  const UploadImage({
    required this.name,
    required this.bytes,
    this.mimeType = 'image/jpeg',
  });
  final String name;
  final Uint8List bytes;
  final String mimeType;
}

/// Everything the app needs from the SpotOn API. The real implementation is
/// [HttpSpotOnApi]; tests use a fake. All calls throw `ApiException` on failure.
abstract interface class SpotOnApi {
  /// Checks that the server answers (used by the server-address screen).
  Future<void> ping();

  // Session
  Future<bool> get hasSession;
  Future<void> register(String email, String password);
  Future<void> login(String email, String password);
  Future<void> logout();
  Future<void> deleteAccount(String password);
  Future<UserInfo> me();

  // Profile
  Future<Profile?> profile();
  Future<Profile> saveProfile(ProfileInput input);

  // Today and tracking
  Future<Today> today({DateTime? day});
  Future<void> addWater(int ml, {DateTime? day});
  Future<void> setSteps(DateTime day, int steps);
  Future<void> logWeight(double kg, {DateTime? day});
  Future<List<WorkoutResult>> logWorkout(String text, {DateTime? day});
  Future<History> history(String period);

  // Meals
  Future<Draft> analyze({String? note, UploadImage? image});
  Future<Meal> saveMeal({
    required String slot,
    required List<FoodItem> items,
    required String source,
    required String idempotencyKey,
    String? note,
    bool isFavourite = false,
    DateTime? eatenAt,
  });
  Future<List<Meal>> meals({DateTime? day});
  Future<List<Meal>> recentMeals();
  Future<List<Meal>> favouriteMeals();
  Future<Meal> setFavourite(String mealId, bool value);
  Future<Meal> updateMeal(
    String mealId, {
    required String slot,
    required List<FoodItem> items,
  });
  Future<Meal> repeatMeal(String mealId);
  Future<void> deleteMeal(String mealId);

  // Coach and suggestions
  Future<Suggestions> suggestions(String mode);
  Stream<CoachEvent> coachStream(String message, String threadId);
  Future<List<ChatMessage>> coachThread(String threadId);

  // My foods, rules, remembered foods
  Future<List<MyFood>> myFoods();
  Future<List<MyFood>> saveMyFoods(List<MyFood> foods);
  Future<List<FoodRule>> rules();
  Future<FoodRule> parseRule(String text);
  Future<FoodRule> saveRule(FoodRule rule);
  Future<void> deleteRule(String id);
  Future<List<RememberedFood>> rememberedFoods();
  Future<void> forgetFood(String id);

  // Progress
  Future<Progress> progress();
  Future<WeeklyReview> weeklyReview();
  Future<void> decideReview(String id, {required bool accept});
  Future<void> logMeasurement({
    double? waistCm,
    double? hipCm,
    double? bodyFatPct,
  });

  // Data
  Future<Uint8List> export(String format);
}
