import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api/spoton_api.dart';
import '../../core/models.dart';
import '../../core/providers.dart';

/// What the user chose to analyze (photo and/or text). Read by the analyzing screen.
class CaptureRequest {
  const CaptureRequest({this.note, this.image});
  final String? note;
  final UploadImage? image;
}

class CaptureRequestNotifier extends Notifier<CaptureRequest?> {
  @override
  CaptureRequest? build() => null;
  void set(CaptureRequest? r) => state = r;
}

final captureRequestProvider =
    NotifierProvider<CaptureRequestNotifier, CaptureRequest?>(
      CaptureRequestNotifier.new,
    );

/// Opens the camera or gallery and returns the photo. Replaced in tests.
typedef PickPhoto = Future<UploadImage?> Function({required bool camera});

final pickPhotoProvider = Provider<PickPhoto>((ref) {
  return ({required bool camera}) async {
    final x = await ImagePicker().pickImage(
      source: camera ? ImageSource.camera : ImageSource.gallery,
      maxWidth: 1600,
      imageQuality: 85,
    );
    if (x == null) return null;
    final bytes = await x.readAsBytes();
    return UploadImage(
      name: x.name.isEmpty ? 'meal.jpg' : x.name,
      bytes: bytes,
      mimeType: x.mimeType ?? 'image/jpeg',
    );
  };
});

/// The meal being reviewed. Items are edited in place; the server recomputes all totals on save.
class DraftState {
  const DraftState({
    required this.items,
    required this.slot,
    required this.source,
    required this.key,
    this.note,
    this.favourite = false,
    this.warnings = const [],
    this.clarify,
    this.oilyItems = const [],
    this.editingMealId,
    this.edited = false,
  });

  final List<FoodItem> items;
  final String slot;

  /// photo | text | repeat
  final String source;

  /// Idempotency key: retrying a save can never create a second meal.
  final String key;
  final String? note, clarify, editingMealId;
  final bool favourite, edited;
  final List<String> warnings, oilyItems;

  Nutrients get total =>
      items.fold(const Nutrients(), (sum, i) => sum + i.total);

  DraftState copyWith({
    List<FoodItem>? items,
    String? slot,
    String? note,
    bool? favourite,
    bool? edited,
  }) => DraftState(
    items: items ?? this.items,
    slot: slot ?? this.slot,
    source: source,
    key: key,
    note: note ?? this.note,
    favourite: favourite ?? this.favourite,
    warnings: warnings,
    clarify: clarify,
    oilyItems: oilyItems,
    editingMealId: editingMealId,
    edited: edited ?? this.edited,
  );
}

class DraftNotifier extends Notifier<DraftState?> {
  @override
  DraftState? build() => null;

  static String _newKey() =>
      DateTime.now().microsecondsSinceEpoch.toRadixString(36) +
      UniqueKeyCounter.next();

  void startFromAnalysis(Draft d, {required String source, String? note}) {
    state = DraftState(
      items: d.items.map((i) => i.copy()).toList(),
      slot: d.mealSlot.isEmpty ? 'snack' : d.mealSlot,
      source: source,
      key: _newKey(),
      note: note,
      warnings: d.warnings,
      clarify: d.clarify,
      oilyItems: d.oilyItems,
    );
  }

  /// A coach suggestion or a saved meal opened for review.
  void startFromItems(
    List<FoodItem> items, {
    required String slot,
    String source = 'text',
    String? editingMealId,
  }) {
    state = DraftState(
      items: items.map((i) => i.copy()).toList(),
      slot: slot,
      source: source,
      key: _newKey(),
      editingMealId: editingMealId,
    );
  }

  void setQuantity(int index, double quantity) {
    final items = [...state!.items];
    items[index] = items[index].copy()..quantity = quantity;
    state = state!.copyWith(items: items, edited: true);
  }

  /// Replaces an item after the user edited it. Changing the name or the per-unit values
  /// marks it "edited", so the server remembers the user's own values for that food.
  void replaceItem(int index, FoodItem edited) {
    final items = [...state!.items];
    final original = items[index];
    final changedFood =
        edited.name != original.name ||
        !edited.perUnit.sameAs(original.perUnit);
    items[index] = edited.copy()
      ..source = changedFood ? 'edited' : original.source;
    state = state!.copyWith(items: items, edited: true);
  }

  void addItem(FoodItem item) {
    state = state!.copyWith(
      items: [...state!.items, item.copy()..source = 'manual'],
      edited: true,
    );
  }

  void removeAt(int index) {
    final items = [...state!.items]..removeAt(index);
    state = state!.copyWith(items: items, edited: true);
  }

  void setSlot(String slot) =>
      state = state!.copyWith(slot: slot, edited: true);
  void setNote(String note) => state = state!.copyWith(note: note);
  void toggleFavourite() =>
      state = state!.copyWith(favourite: !state!.favourite);
  void clear() => state = null;

  /// Saves (or updates) the meal, then refreshes every screen. Throws ApiException.
  Future<Meal> save() async {
    final d = state!;
    final api = ref.read(apiProvider);
    final meal = d.editingMealId != null
        ? await api.updateMeal(d.editingMealId!, slot: d.slot, items: d.items)
        : await api.saveMeal(
            slot: d.slot,
            items: d.items,
            source: d.source,
            idempotencyKey: d.key,
            note: d.note,
            isFavourite: d.favourite,
          );
    state = null;
    ref.read(dataVersion.notifier).bump();
    return meal;
  }
}

final draftProvider = NotifierProvider<DraftNotifier, DraftState?>(
  DraftNotifier.new,
);

/// Makes idempotency keys unique even within the same microsecond.
class UniqueKeyCounter {
  static int _n = 0;
  static String next() => (_n++).toRadixString(36);
}
