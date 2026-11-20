// Typed models for the SpotOn API. Shapes are checked against real API responses in
// test/contract_test.dart (fixtures come from scripts/gen_mobile_fixtures.py).

double _d(Object? v) => (v as num?)?.toDouble() ?? 0;
int _i(Object? v) => (v as num?)?.toInt() ?? 0;
String _s(Object? v) => (v as String?) ?? '';
Map<String, dynamic> _m(Object? v) =>
    (v as Map?)?.cast<String, dynamic>() ?? const {};
List<Map<String, dynamic>> _ml(Object? v) => ((v as List?) ?? const [])
    .map((e) => (e as Map).cast<String, dynamic>())
    .toList();

/// Calories and macros. Used both for "per unit" values and for totals.
class Nutrients {
  const Nutrients({
    this.kcal = 0,
    this.protein = 0,
    this.carbs = 0,
    this.fat = 0,
    this.fibre = 0,
  });

  final double kcal, protein, carbs, fat, fibre;

  factory Nutrients.fromJson(Map<String, dynamic> j) => Nutrients(
    kcal: _d(j['kcal']),
    protein: _d(j['protein'] ?? j['protein_g']),
    carbs: _d(j['carbs'] ?? j['carbs_g']),
    fat: _d(j['fat'] ?? j['fat_g']),
    fibre: _d(j['fibre'] ?? j['fibre_g']),
  );

  Nutrients operator *(double f) => Nutrients(
    kcal: kcal * f,
    protein: protein * f,
    carbs: carbs * f,
    fat: fat * f,
    fibre: fibre * f,
  );

  Nutrients operator +(Nutrients o) => Nutrients(
    kcal: kcal + o.kcal,
    protein: protein + o.protein,
    carbs: carbs + o.carbs,
    fat: fat + o.fat,
    fibre: fibre + o.fibre,
  );

  Nutrients copyWith({
    double? kcal,
    double? protein,
    double? carbs,
    double? fat,
    double? fibre,
  }) => Nutrients(
    kcal: kcal ?? this.kcal,
    protein: protein ?? this.protein,
    carbs: carbs ?? this.carbs,
    fat: fat ?? this.fat,
    fibre: fibre ?? this.fibre,
  );

  bool sameAs(Nutrients o, {double tolerance = 1e-6}) =>
      (kcal - o.kcal).abs() <= tolerance &&
      (protein - o.protein).abs() <= tolerance &&
      (carbs - o.carbs).abs() <= tolerance &&
      (fat - o.fat).abs() <= tolerance &&
      (fibre - o.fibre).abs() <= tolerance;

  Map<String, dynamic> toJson() => {
    'kcal': kcal,
    'protein': protein,
    'carbs': carbs,
    'fat': fat,
    'fibre': fibre,
  };
}

/// One food in a meal. `perUnit` is ONE unit (one egg); totals are quantity x perUnit,
/// which the server recomputes on save.
class FoodItem {
  FoodItem({
    required this.name,
    required this.quantity,
    required this.unit,
    required this.perUnit,
    this.gramsPerUnit,
    this.oilLevel = 'none',
    this.remark,
    this.source = 'ai_estimate',
    this.confidence,
    this.sizeFactor = 1,
  });

  String name;
  double quantity;
  String unit;
  double? gramsPerUnit;
  Nutrients perUnit;
  String oilLevel;
  String? remark;

  /// ai_estimate | memory | edited | manual
  String source;
  double? confidence;

  /// Portion size picked on the review screen (1 = as estimated). App-only: the saved
  /// per-unit values already include it.
  double sizeFactor;

  Nutrients get total => perUnit * quantity;
  bool get isOily => oilLevel == 'medium' || oilLevel == 'heavy';

  factory FoodItem.fromJson(Map<String, dynamic> j) => FoodItem(
    name: _s(j['name']),
    quantity: _d(j['quantity']),
    unit: _s(j['unit']).isEmpty ? 'serving' : _s(j['unit']),
    gramsPerUnit: (j['grams_per_unit'] as num?)?.toDouble(),
    perUnit: Nutrients.fromJson(_m(j['per_unit'])),
    oilLevel: _s(j['oil_level']).isEmpty ? 'none' : _s(j['oil_level']),
    remark: j['remark'] as String?,
    source: _s(j['source']).isEmpty ? 'ai_estimate' : _s(j['source']),
    confidence: (j['confidence'] as num?)?.toDouble(),
  );

  FoodItem copy() => FoodItem(
    name: name,
    quantity: quantity,
    unit: unit,
    perUnit: perUnit,
    gramsPerUnit: gramsPerUnit,
    oilLevel: oilLevel,
    remark: remark,
    source: source,
    confidence: confidence,
    sizeFactor: sizeFactor,
  );

  /// The body the API's POST /v1/meals expects for one item.
  Map<String, dynamic> toSaveJson() => {
    'name': name,
    'quantity': quantity,
    'unit': unit,
    if (gramsPerUnit != null) 'grams_per_unit': gramsPerUnit,
    'per_unit': perUnit.toJson(),
    'oil_level': oilLevel,
    if (remark != null) 'remark': remark,
    'source': source,
  };
}

class Meal {
  const Meal({
    required this.id,
    required this.eatenAt,
    required this.slot,
    required this.items,
    required this.totals,
    this.note,
    this.source = 'text',
    this.isFavourite = false,
  });

  final String id;
  final DateTime eatenAt;
  final String slot;
  final String? note;
  final String source;
  final bool isFavourite;
  final List<FoodItem> items;
  final Nutrients totals;

  factory Meal.fromJson(Map<String, dynamic> j) => Meal(
    id: _s(j['id']),
    eatenAt: DateTime.parse(_s(j['eaten_at'])),
    slot: _s(j['slot']),
    note: j['note'] as String?,
    source: _s(j['source']),
    isFavourite: j['is_favourite'] == true,
    items: _ml(j['items']).map(FoodItem.fromJson).toList(),
    totals: Nutrients.fromJson(_m(j['totals'])),
  );

  String get summary => items.map((i) => i.name).join(', ');
}

/// What POST /v1/meals/analyze returns. Nothing is saved until the user confirms.
class Draft {
  const Draft({
    required this.items,
    required this.mealSlot,
    this.oilyItems = const [],
    this.warnings = const [],
    this.clarify,
  });

  final List<FoodItem> items;
  final String mealSlot;
  final List<String> oilyItems;
  final List<String> warnings;

  /// Every food is one the user already confirmed (their remembered values) and the model
  /// raised nothing to check, so the meal can be saved without the review screen.
  bool get allRemembered =>
      items.isNotEmpty &&
      items.every((i) => i.source == 'memory') &&
      warnings.isEmpty &&
      oilyItems.isEmpty &&
      clarify == null;
  final String? clarify;

  factory Draft.fromJson(Map<String, dynamic> j) => Draft(
    items: _ml(j['items']).map(FoodItem.fromJson).toList(),
    mealSlot: _s(j['meal_slot']),
    oilyItems: ((j['oily_items'] as List?) ?? const []).cast<String>(),
    warnings: ((j['warnings'] as List?) ?? const []).cast<String>(),
    clarify: j['clarify'] as String?,
  );
}

class Targets {
  const Targets({
    required this.bmi,
    required this.bmr,
    required this.maintenance,
    required this.kcal,
    required this.kcalFloor,
    required this.proteinG,
    required this.fatG,
    required this.carbsG,
    required this.fibreG,
    required this.waterMl,
    required this.steps,
    this.kcalAdjustment = 0,
    this.stepsAdjustment = 0,
    this.maintenanceSource = 'formula',
  });

  final double bmi, bmr, maintenance;
  final int kcal, kcalFloor, proteinG, fatG, carbsG, fibreG, waterMl, steps;
  final int kcalAdjustment, stepsAdjustment;
  final String maintenanceSource;

  factory Targets.fromJson(Map<String, dynamic> j) => Targets(
    bmi: _d(j['bmi']),
    bmr: _d(j['bmr']),
    maintenance: _d(j['maintenance']),
    kcal: _i(j['kcal']),
    kcalFloor: _i(j['kcal_floor']),
    proteinG: _i(j['protein_g']),
    fatG: _i(j['fat_g']),
    carbsG: _i(j['carbs_g']),
    fibreG: _i(j['fibre_g']),
    waterMl: _i(j['water_ml']),
    steps: _i(j['steps']),
    kcalAdjustment: _i(j['kcal_adjustment']),
    stepsAdjustment: _i(j['steps_adjustment']),
    maintenanceSource: _s(j['maintenance_source']).isEmpty
        ? 'formula'
        : _s(j['maintenance_source']),
  );
}

/// The user's inputs. Also used as the editable form state (onboarding and edit profile).
class ProfileInput {
  ProfileInput({
    this.age = 30,
    this.sex = 'male',
    this.heightCm = 170,
    this.weightKg = 70,
    this.goal = 'lose_fat',
    this.activity = 'light',
    this.bodyFatPct,
    this.goalWeightKg,
    this.baselineSteps = 5000,
  });

  int age;
  String sex;
  double heightCm;
  double weightKg;
  String goal;
  String activity;
  double? bodyFatPct;
  double? goalWeightKg;
  int baselineSteps;

  factory ProfileInput.fromJson(Map<String, dynamic> j) => ProfileInput(
    age: _i(j['age']),
    sex: _s(j['sex']),
    heightCm: _d(j['height_cm']),
    weightKg: _d(j['weight_kg']),
    goal: _s(j['goal']),
    activity: _s(j['activity']),
    bodyFatPct: (j['body_fat_pct'] as num?)?.toDouble(),
    goalWeightKg: (j['goal_weight_kg'] as num?)?.toDouble(),
    baselineSteps: _i(j['baseline_steps']),
  );

  ProfileInput copy() => ProfileInput(
    age: age,
    sex: sex,
    heightCm: heightCm,
    weightKg: weightKg,
    goal: goal,
    activity: activity,
    bodyFatPct: bodyFatPct,
    goalWeightKg: goalWeightKg,
    baselineSteps: baselineSteps,
  );

  Map<String, dynamic> toJson() => {
    'age': age,
    'sex': sex,
    'height_cm': heightCm,
    'weight_kg': weightKg,
    'goal': goal,
    'activity': activity,
    'body_fat_pct': bodyFatPct,
    'goal_weight_kg': goalWeightKg,
    'baseline_steps': baselineSteps,
  };
}

class Profile {
  const Profile({
    required this.input,
    required this.targets,
    this.warnings = const [],
  });

  final ProfileInput input;
  final Targets targets;
  final List<String> warnings;

  factory Profile.fromJson(Map<String, dynamic> j) => Profile(
    input: ProfileInput.fromJson(j),
    targets: Targets.fromJson(_m(j['targets'])),
    warnings: ((j['warnings'] as List?) ?? const []).cast<String>(),
  );
}

class UserInfo {
  const UserInfo({
    required this.id,
    required this.email,
    required this.timezone,
  });
  final String id, email, timezone;
  factory UserInfo.fromJson(Map<String, dynamic> j) => UserInfo(
    id: _s(j['id']),
    email: _s(j['email']),
    timezone: _s(j['timezone']).isEmpty ? 'UTC' : _s(j['timezone']),
  );
}

class Today {
  const Today({
    required this.day,
    required this.eaten,
    required this.leftKcal,
    required this.leftProteinG,
    required this.targets,
    required this.waterMl,
    required this.steps,
    required this.burnedKcal,
    this.workoutMin = 0,
    this.nudges = const [],
    this.meals,
    this.weeklyReview,
  });

  final DateTime day;
  final Nutrients eaten;
  final double leftKcal, leftProteinG;
  final Targets targets;
  final int waterMl, steps;
  final double burnedKcal, workoutMin;
  final List<String> nudges;

  /// The day's meals and (for today) the weekly review, sent with Today so the screen needs
  /// one call. Null from an older server: the app then fetches them separately.
  final List<Meal>? meals;
  final WeeklyReview? weeklyReview;

  factory Today.fromJson(Map<String, dynamic> j) {
    final left = _m(j['left']);
    return Today(
      day: DateTime.parse(_s(j['day'])),
      eaten: Nutrients.fromJson(_m(j['eaten'])),
      leftKcal: _d(left['kcal']),
      leftProteinG: _d(left['protein_g']),
      targets: Targets.fromJson(_m(j['targets'])),
      waterMl: _i(j['water_ml']),
      steps: _i(j['steps']),
      burnedKcal: _d(j['burned_kcal_est']),
      workoutMin: _d(j['workout_min']),
      nudges: ((j['nudges'] as List?) ?? const []).cast<String>(),
      meals: j['meals'] is List
          ? (j['meals'] as List).map((m) => Meal.fromJson(_m(m))).toList()
          : null,
      weeklyReview: j['weekly_review'] is Map
          ? WeeklyReview.fromJson(_m(j['weekly_review']))
          : null,
    );
  }
}

class WorkoutResult {
  const WorkoutResult({
    required this.activity,
    required this.minutes,
    required this.kcal,
  });
  final String activity;
  final double minutes, kcal;
  factory WorkoutResult.fromJson(Map<String, dynamic> j) => WorkoutResult(
    activity: _s(j['activity']),
    minutes: _d(j['minutes']),
    kcal: _d(j['kcal']),
  );
}

class HistoryPoint {
  const HistoryPoint({
    required this.date,
    required this.kcal,
    required this.protein,
    required this.steps,
    required this.daysLogged,
    this.weightKg,
  });
  final DateTime date;
  final double kcal, protein, steps;
  final int daysLogged;
  final double? weightKg;
}

class History {
  const History({
    required this.period,
    required this.points,
    required this.daysLogged,
  });
  final String period;
  final List<HistoryPoint> points;
  final int daysLogged;

  factory History.fromJson(Map<String, dynamic> j) {
    final period = _s(j['period']);
    final points = _ml(j['rows']).map((r) {
      final logged = r.containsKey('logged')
          ? (r['logged'] == true ? 1 : 0)
          : _i(r['days_logged']);
      return HistoryPoint(
        date: DateTime.parse(
          _s(r[period]).isEmpty ? _s(r['day']) : _s(r[period]),
        ),
        kcal: _d(r['kcal']),
        protein: _d(r['protein']),
        steps: _d(r['steps']),
        daysLogged: logged,
        weightKg: ((r['weight_kg'] ?? r['avg_weight_kg']) as num?)?.toDouble(),
      );
    }).toList();
    return History(
      period: period,
      points: points,
      daysLogged: _i(j['days_logged']),
    );
  }
}

class WeightPoint {
  const WeightPoint({required this.day, required this.trendKg, this.kg});
  final DateTime day;
  final double trendKg;
  final double? kg;
}

class Maintenance {
  const Maintenance({
    required this.active,
    required this.kcal,
    required this.formulaKcal,
    required this.explanation,
  });
  final bool active;
  final double kcal, formulaKcal;
  final String explanation;
}

class Measurement {
  const Measurement({
    required this.day,
    this.waistCm,
    this.hipCm,
    this.bodyFatPct,
  });
  final DateTime day;
  final double? waistCm, hipCm, bodyFatPct;
  factory Measurement.fromJson(Map<String, dynamic> j) => Measurement(
    day: DateTime.parse(_s(j['day'])),
    waistCm: (j['waist_cm'] as num?)?.toDouble(),
    hipCm: (j['hip_cm'] as num?)?.toDouble(),
    bodyFatPct: (j['body_fat_pct'] as num?)?.toDouble(),
  );
}

class Progress {
  const Progress({
    required this.latestKg,
    required this.trendKg,
    required this.trendChange4wKg,
    required this.series,
    required this.maintenance,
    required this.measurements,
    this.predictionMessage,
    this.rangeWeeks,
    this.rangeLowKg,
    this.rangeHighKg,
  });

  final double? latestKg, trendKg, trendChange4wKg;
  final List<WeightPoint> series;
  final Maintenance maintenance;
  final List<Measurement> measurements;
  final String? predictionMessage;
  final int? rangeWeeks;
  final double? rangeLowKg, rangeHighKg;

  factory Progress.fromJson(Map<String, dynamic> j) {
    final w = _m(j['weight']);
    final m = _m(j['maintenance']);
    final inWeeks = j['in_weeks'] == null ? null : _m(j['in_weeks']);
    return Progress(
      latestKg: (w['latest_kg'] as num?)?.toDouble(),
      trendKg: (w['trend_kg'] as num?)?.toDouble(),
      trendChange4wKg: (w['trend_change_4w_kg'] as num?)?.toDouble(),
      series: _ml(w['series'])
          .map(
            (p) => WeightPoint(
              day: DateTime.parse(_s(p['day'])),
              trendKg: _d(p['trend_kg']),
              kg: (p['kg'] as num?)?.toDouble(),
            ),
          )
          .toList(),
      maintenance: Maintenance(
        active: m['active'] == true,
        kcal: _d(m['kcal']),
        formulaKcal: _d(m['formula_kcal']),
        explanation: _s(m['explanation']),
      ),
      measurements: _ml(j['measurements']).map(Measurement.fromJson).toList(),
      predictionMessage: j['prediction'] == null
          ? null
          : _s(_m(j['prediction'])['message']),
      rangeWeeks: inWeeks == null ? null : _i(inWeeks['weeks']),
      rangeLowKg: (inWeeks?['low_kg'] as num?)?.toDouble(),
      rangeHighKg: (inWeeks?['high_kg'] as num?)?.toDouble(),
    );
  }
}

class Proposal {
  const Proposal({
    required this.kind,
    required this.delta,
    required this.text,
    required this.reason,
  });
  final String kind;
  final int delta;
  final String text, reason;
  factory Proposal.fromJson(Map<String, dynamic> j) => Proposal(
    kind: _s(j['kind']),
    delta: _i(j['delta']),
    text: _s(j['text']),
    reason: _s(j['reason']),
  );
}

class Review {
  const Review({
    required this.id,
    required this.weekStart,
    required this.weekEnd,
    required this.daysLogged,
    required this.avgKcal,
    required this.kcalTarget,
    required this.proteinHitDays,
    required this.proteinTargetG,
    required this.notes,
    this.trendEndKg,
    this.trendChangeKg,
    this.waistChangeCm,
    this.proposal,
    this.decision,
  });

  final String id;
  final DateTime weekStart, weekEnd;
  final int daysLogged, kcalTarget, proteinHitDays, proteinTargetG;
  final int? avgKcal;
  final double? trendEndKg, trendChangeKg, waistChangeCm;
  final List<String> notes;
  final Proposal? proposal;
  final String? decision;

  bool get awaitingDecision => proposal != null && decision == null;

  factory Review.fromJson(Map<String, dynamic> j) {
    final s = _m(j['summary']);
    return Review(
      id: _s(j['id']),
      weekStart: DateTime.parse(_s(s['week_start'])),
      weekEnd: DateTime.parse(_s(s['week_end'])),
      daysLogged: _i(s['days_logged']),
      avgKcal: (s['avg_kcal'] as num?)?.toInt(),
      kcalTarget: _i(s['kcal_target']),
      proteinHitDays: _i(s['protein_hit_days']),
      proteinTargetG: _i(s['protein_target_g']),
      trendEndKg: (s['trend_end_kg'] as num?)?.toDouble(),
      trendChangeKg: (s['trend_change_kg'] as num?)?.toDouble(),
      waistChangeCm: (s['waist_change_cm'] as num?)?.toDouble(),
      notes: ((s['notes'] as List?) ?? const []).cast<String>(),
      proposal: j['proposal'] == null
          ? null
          : Proposal.fromJson(_m(j['proposal'])),
      decision: j['decision'] as String?,
    );
  }
}

class WeeklyReview {
  const WeeklyReview({this.review, required this.nextReviewOn});
  final Review? review;
  final DateTime nextReviewOn;
  bool get pendingDecision => review?.awaitingDecision ?? false;

  factory WeeklyReview.fromJson(Map<String, dynamic> j) => WeeklyReview(
    review: j['review'] == null ? null : Review.fromJson(_m(j['review'])),
    nextReviewOn: DateTime.parse(_s(j['next_review_on'])),
  );
}

class SuggestionOption {
  const SuggestionOption({
    required this.title,
    required this.why,
    required this.items,
    required this.totals,
    required this.fits,
  });
  final String title, why;
  final List<FoodItem> items;
  final Nutrients totals;
  final bool fits;

  factory SuggestionOption.fromJson(Map<String, dynamic> j) => SuggestionOption(
    title: _s(j['title']),
    why: _s(j['why']),
    items: _ml(j['items']).map(FoodItem.fromJson).toList(),
    totals: Nutrients.fromJson(_m(j['totals'])),
    fits: j['fits'] == true,
  );
}

class Suggestions {
  const Suggestions({
    required this.mode,
    required this.leftKcal,
    required this.leftProteinG,
    required this.options,
    this.note,
  });
  final String mode;
  final double leftKcal, leftProteinG;
  final List<SuggestionOption> options;
  final String? note;

  factory Suggestions.fromJson(Map<String, dynamic> j) {
    final left = _m(j['left']);
    return Suggestions(
      mode: _s(j['mode']),
      leftKcal: _d(left['kcal']),
      leftProteinG: _d(left['protein_g']),
      options: _ml(j['options']).map(SuggestionOption.fromJson).toList(),
      note: j['note'] as String?,
    );
  }
}

class FoodRule {
  const FoodRule({
    required this.kind,
    required this.food,
    required this.summary,
    required this.originalText,
    this.id,
    this.limit,
    this.time,
    this.state,
    this.blocksNow = false,
    this.status,
  });

  final String? id;
  final String kind, food, summary, originalText;
  final int? limit;
  final String? time;

  /// ok | at_limit | broken (only on rules the server already stores)
  final String? state;
  final bool blocksNow;
  final String? status;

  factory FoodRule.fromJson(Map<String, dynamic> j) => FoodRule(
    id: j['id'] as String?,
    kind: _s(j['kind']),
    food: _s(j['food']),
    summary: _s(j['summary']),
    originalText: _s(j['original_text']),
    limit: (j['limit'] as num?)?.toInt(),
    time: j['time'] as String?,
    state: j['state'] as String?,
    blocksNow: j['blocks_now'] == true,
    status: j['status'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'kind': kind,
    'food': food,
    'limit': limit,
    'time': time,
    'summary': summary,
    'original_text': originalText,
  };
}

class MyFood {
  const MyFood({
    required this.name,
    this.id,
    this.effort = 'no_cook',
    this.slots = const [],
    this.available = true,
  });
  final String? id;
  final String name, effort;
  final List<String> slots;
  final bool available;

  factory MyFood.fromJson(Map<String, dynamic> j) => MyFood(
    id: j['id'] as String?,
    name: _s(j['name']),
    effort: _s(j['effort']),
    slots: ((j['slots'] as List?) ?? const []).cast<String>(),
    available: j['available'] != false,
  );

  MyFood copyWith({
    String? name,
    String? effort,
    List<String>? slots,
    bool? available,
  }) => MyFood(
    id: id,
    name: name ?? this.name,
    effort: effort ?? this.effort,
    slots: slots ?? this.slots,
    available: available ?? this.available,
  );

  Map<String, dynamic> toJson() => {
    'name': name,
    'effort': effort,
    'slots': slots,
    'available': available,
  };
}

class RememberedFood {
  const RememberedFood({
    required this.id,
    required this.name,
    required this.unit,
    required this.kcal,
    required this.protein,
    required this.timesUsed,
  });
  final String id, name, unit;
  final double kcal, protein;
  final int timesUsed;
  factory RememberedFood.fromJson(Map<String, dynamic> j) => RememberedFood(
    id: _s(j['id']),
    name: _s(j['name']),
    unit: _s(j['unit']),
    kcal: _d(j['kcal']),
    protein: _d(j['protein']),
    timesUsed: _i(j['times_used']),
  );
}

class ChatMessage {
  const ChatMessage({
    required this.role,
    required this.content,
    this.safety = false,
  });
  final String role; // user | assistant
  final String content;
  final bool safety;
  bool get isUser => role == 'user';
  ChatMessage copyWith({String? content, bool? safety}) => ChatMessage(
    role: role,
    content: content ?? this.content,
    safety: safety ?? this.safety,
  );
}

/// Events from the coach's Server-Sent-Events stream.
sealed class CoachEvent {
  const CoachEvent();
}

class CoachStatus extends CoachEvent {
  const CoachStatus(this.tool);
  final String tool;
}

class CoachToken extends CoachEvent {
  const CoachToken(this.text);
  final String text;
}

class CoachDone extends CoachEvent {
  const CoachDone(this.reply, {this.safety});
  final String reply;
  final String? safety;
}

class CoachFailed extends CoachEvent {
  const CoachFailed(this.message);
  final String message;
}

class AuthTokens {
  const AuthTokens({required this.accessToken, required this.refreshToken});
  final String accessToken, refreshToken;
  factory AuthTokens.fromJson(Map<String, dynamic> j) => AuthTokens(
    accessToken: _s(j['access_token']),
    refreshToken: _s(j['refresh_token']),
  );
}
