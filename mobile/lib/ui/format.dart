import 'package:intl/intl.dart';

final _int = NumberFormat('#,##0');

/// 1,234 (rounded).
String fmtInt(num v) => _int.format(v.round());

/// 6.3 / 72 / 1.5: one decimal at most, no trailing ".0".
String fmtNum(num v) {
  final r = (v * 10).round() / 10;
  return r == r.roundToDouble() ? _int.format(r.round()) : r.toStringAsFixed(1);
}

const slotNames = {
  'breakfast': 'Breakfast',
  'snack': 'Snack',
  'lunch': 'Lunch',
  'pre_workout': 'Pre-workout',
  'dinner': 'Dinner',
  'bedtime': 'Bedtime',
};
String slotLabel(String slot) => slotNames[slot] ?? slot;

const mealSlots = [
  'breakfast',
  'snack',
  'lunch',
  'pre_workout',
  'dinner',
  'bedtime',
];

String dayTitle(DateTime day, DateTime today) {
  final d = DateTime(day.year, day.month, day.day);
  final t = DateTime(today.year, today.month, today.day);
  final diff = t.difference(d).inDays;
  if (diff == 0) return 'Today';
  if (diff == 1) return 'Yesterday';
  return DateFormat('EEE, d MMM').format(d);
}

String shortDate(DateTime d) => DateFormat('d MMM').format(d);
String longDate(DateTime d) => DateFormat('EEEE, d MMMM').format(d);
String clock(DateTime t) => DateFormat('HH:mm').format(t);

String signed(num v, {int digits = 1, String unit = ''}) {
  final s = v.toStringAsFixed(digits);
  final text = v > 0 ? '+$s' : s;
  return unit.isEmpty ? text : '$text $unit';
}
