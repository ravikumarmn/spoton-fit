import 'dart:async';
import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:material_ui/material_ui.dart';

import '../core/api_error.dart';
import 'format.dart';
import 'theme.dart';

/// Turns any error into a sentence for the user.
String errorMessage(Object error) => error is ApiException
    ? error.message
    : 'Something went wrong. Please try again.';

void showToast(BuildContext context, String message, {SnackBarAction? action}) {
  final m = ScaffoldMessenger.of(context);
  m.hideCurrentSnackBar();
  m.showSnackBar(
    SnackBar(
      content: Text(message),
      action: action,
      duration: const Duration(seconds: 5),
    ),
  );
}

// --- Cards and text -------------------------------------------------------------------

class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.onTap,
    this.color,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppSpace.radiusCard),
      side: const BorderSide(color: AppColors.outline),
    );
    return Material(
      color: color ?? AppColors.surface,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: onTap == null
          ? Padding(padding: padding, child: child)
          : InkWell(
              onTap: onTap,
              child: Padding(padding: padding, child: child),
            ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final title = Semantics(
      header: true,
      child: Text(text, style: AppText.section),
    );
    if (trailing == null) return title;
    // Wrap: at large text sizes the action moves under the title instead of overflowing.
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 12,
      runSpacing: 4,
      children: [title, trailing!],
    );
  }
}

// --- Buttons ----------------------------------------------------------------------------

/// The one filled button on a screen.
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.loading = false,
    this.icon,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final child = loading
        ? const SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: AppColors.onPrimary,
            ),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 20),
                const SizedBox(width: 8),
              ],
              Flexible(child: Text(label, textAlign: TextAlign.center)),
            ],
          );
    return FilledButton(onPressed: loading ? null : onPressed, child: child);
  }
}

class SecondaryButton extends StatelessWidget {
  const SecondaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
  });
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;

  @override
  Widget build(BuildContext context) => OutlinedButton(
    onPressed: onPressed,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[Icon(icon, size: 20), const SizedBox(width: 8)],
        Flexible(child: Text(label, textAlign: TextAlign.center)),
      ],
    ),
  );
}

/// Pill used for quick actions, filters and choices. Hit area is at least 48 dp tall.
class AppChip extends StatelessWidget {
  const AppChip({
    super.key,
    required this.label,
    this.onTap,
    this.selected = false,
    this.icon,
  });

  final String label;
  final VoidCallback? onTap;
  final bool selected;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final fg = selected ? AppColors.onContainer : AppColors.text;
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      child: ExcludeSemantics(
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppSpace.minTap / 2),
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              minHeight: AppSpace.minTap,
              minWidth: AppSpace.minTap,
            ),
            child: Center(
              widthFactor: 1,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: selected ? AppColors.container : AppColors.surface,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: selected ? AppColors.container : AppColors.outline,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (icon != null) ...[
                      Icon(icon, size: 18, color: fg),
                      const SizedBox(width: 6),
                    ],
                    Flexible(
                      child: Text(
                        label,
                        style: AppText.label.copyWith(color: fg),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// --- Counts ----------------------------------------------------------------------------

/// − value + control for the number of units (two eggs, three idlis).
class QuantityStepper extends StatelessWidget {
  const QuantityStepper({
    super.key,
    required this.value,
    required this.onChanged,
    required this.itemName,
  });

  final double value;
  final ValueChanged<double> onChanged;
  final String itemName;

  double get _down => value > 1 ? value - 1 : (value > 0.5 ? 0.5 : value);
  double get _up => value < 1 ? 1 : value + 1;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.outline),
        color: AppColors.surface,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _StepButton(
            icon: Icons.remove,
            label: 'Less $itemName',
            enabled: value > 0.5,
            onTap: () => onChanged(_down),
          ),
          Semantics(
            label: '${fmtNum(value)} $itemName',
            child: ExcludeSemantics(
              child: SizedBox(
                width: 36,
                child: Text(
                  fmtNum(value),
                  textAlign: TextAlign.center,
                  style: AppText.number,
                ),
              ),
            ),
          ),
          _StepButton(
            icon: Icons.add,
            label: 'More $itemName',
            enabled: true,
            onTap: () => onChanged(_up),
          ),
        ],
      ),
    );
  }
}

/// A − / + button. Holding it repeats (backlog: long-press to repeat), so 12 rotis
/// don't need 12 taps.
class _StepButton extends StatefulWidget {
  const _StepButton({
    required this.icon,
    required this.label,
    required this.enabled,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final bool enabled;
  final VoidCallback onTap;

  @override
  State<_StepButton> createState() => _StepButtonState();
}

class _StepButtonState extends State<_StepButton> {
  Timer? _repeat;

  void _start() {
    _repeat?.cancel();
    // widget.onTap is read each tick: the parent rebuilds with the new value.
    _repeat = Timer.periodic(const Duration(milliseconds: 180), (_) {
      if (widget.enabled) {
        widget.onTap();
      } else {
        _stop();
      }
    });
  }

  void _stop() {
    _repeat?.cancel();
    _repeat = null;
  }

  @override
  void dispose() {
    _stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final icon = widget.icon;
    final enabled = widget.enabled;
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      child: ExcludeSemantics(
        child: GestureDetector(
          onLongPressStart: enabled ? (_) => _start() : null,
          onLongPressEnd: (_) => _stop(),
          onLongPressCancel: _stop,
          child: InkResponse(
            onTap: enabled ? widget.onTap : null,
            radius: 28,
            child: SizedBox(
              width: AppSpace.minTap,
              height: AppSpace.minTap,
              child: Icon(
                icon,
                size: 22,
                color: enabled ? AppColors.primary : AppColors.outline,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// --- Progress ---------------------------------------------------------------------------

/// A labelled bar: the numbers are always in words, never colour alone.
class MacroBar extends StatelessWidget {
  const MacroBar({
    super.key,
    required this.label,
    required this.value,
    required this.target,
    required this.unit,
    required this.color,
    this.showLeft = false,
  });

  final String label, unit;
  final double value, target;
  final Color color;
  final bool showLeft;

  @override
  Widget build(BuildContext context) {
    final t = target <= 0 ? 1.0 : target;
    final left = t - value;
    final detail =
        '${fmtInt(value)} / ${fmtInt(t)} $unit'
        '${showLeft ? (left >= 0 ? ' · ${fmtInt(left)} left' : ' · ${fmtInt(-left)} over') : ''}';
    return Semantics(
      label: '$label: $detail',
      child: ExcludeSemantics(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(label, style: AppText.label)),
                Flexible(
                  child: Text(
                    detail,
                    style: AppText.caption,
                    textAlign: TextAlign.end,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: LinearProgressIndicator(
                value: (value / t).clamp(0.0, 1.0),
                minHeight: 8,
                color: color,
                backgroundColor: AppColors.track,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Ring for calories eaten vs target. Over target turns amber (never red).
class CalorieRing extends StatelessWidget {
  const CalorieRing({
    super.key,
    required this.eaten,
    required this.target,
    this.size = 96,
  });
  final double eaten, target, size;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: size,
    height: size,
    child: CustomPaint(painter: _RingPainter(target <= 0 ? 0 : eaten / target)),
  );
}

class _RingPainter extends CustomPainter {
  _RingPainter(this.fraction);
  final double fraction;

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 12.0;
    final rect = Offset.zero & size;
    final arc = rect.deflate(stroke / 2);
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..color = AppColors.track;
    canvas.drawArc(arc, 0, math.pi * 2, false, track);
    final f = fraction.clamp(0.0, 1.0);
    if (f > 0) {
      final p = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = stroke
        ..color = fraction > 1 ? AppColors.amber : AppColors.primary;
      canvas.drawArc(arc, -math.pi / 2, math.pi * 2 * f, false, p);
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.fraction != fraction;
}

// --- Messages --------------------------------------------------------------------------

enum BannerKind { warn, info, soft, error }

class InfoBanner extends StatelessWidget {
  const InfoBanner(
    this.text, {
    super.key,
    this.kind = BannerKind.info,
    this.icon,
    this.child,
  });
  final String text;
  final BannerKind kind;
  final IconData? icon;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final (bg, fg, defaultIcon) = switch (kind) {
      BannerKind.warn => (
        AppColors.warnBg,
        AppColors.warn,
        Icons.error_outline,
      ),
      BannerKind.info => (AppColors.infoBg, AppColors.info, Icons.info_outline),
      BannerKind.soft => (
        AppColors.container,
        AppColors.onContainer,
        Icons.lightbulb_outline,
      ),
      BannerKind.error => (
        AppColors.errorBg,
        AppColors.error,
        Icons.error_outline,
      ),
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSpace.radiusButton),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon ?? defaultIcon, size: 20, color: fg),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  text,
                  style: AppText.label.copyWith(
                    color: fg,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                ?child,
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.message,
    this.action,
  });
  final IconData icon;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(24),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 40, color: AppColors.text3),
        const SizedBox(height: 12),
        Text(
          message,
          textAlign: TextAlign.center,
          style: AppText.body.copyWith(color: AppColors.text2),
        ),
        if (action != null) ...[const SizedBox(height: 16), action!],
      ],
    ),
  );
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, this.onRetry});
  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => Center(
    child: EmptyState(
      icon: Icons.cloud_off_outlined,
      message: errorMessage(error),
      action: onRetry == null
          ? null
          : SecondaryButton(label: 'Try again', onPressed: onRetry),
    ),
  );
}

/// Renders an AsyncValue with consistent loading and error states.
class AsyncView<T> extends StatelessWidget {
  const AsyncView({
    super.key,
    required this.value,
    required this.builder,
    this.onRetry,
  });
  final AsyncValue<T> value;
  final Widget Function(T data) builder;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => value.when(
    data: builder,
    loading: () => const Center(child: CircularProgressIndicator()),
    error: (e, _) => ErrorView(error: e, onRetry: onRetry),
  );
}

// --- Sheets and dialogs --------------------------------------------------------------

/// Bottom sheet that lifts above the keyboard and scrolls when needed.
Future<T?> showAppSheet<T>(
  BuildContext context, {
  required WidgetBuilder builder,
}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (ctx) => Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        0,
        16,
        16 + MediaQuery.viewInsetsOf(ctx).bottom,
      ),
      child: SingleChildScrollView(child: builder(ctx)),
    ),
  );
}

Future<bool> confirm(
  BuildContext context, {
  required String title,
  required String message,
  required String confirmLabel,
  String cancelLabel = 'Cancel',
  bool destructive = false,
}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: Text(cancelLabel),
        ),
        TextButton(
          onPressed: () => Navigator.pop(ctx, true),
          style: destructive
              ? TextButton.styleFrom(foregroundColor: AppColors.error)
              : null,
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return ok ?? false;
}

/// A text field with a number keyboard and a clear validation message.
class NumberField extends StatelessWidget {
  const NumberField({
    super.key,
    required this.controller,
    required this.label,
    this.suffix,
    this.min,
    this.max,
    this.required = true,
    this.decimals = true,
    this.helper,
    this.textInputAction = TextInputAction.next,
  });

  final TextEditingController controller;
  final String label;
  final String? suffix, helper;
  final double? min, max;
  final bool required, decimals;
  final TextInputAction textInputAction;

  @override
  Widget build(BuildContext context) => TextFormField(
    controller: controller,
    keyboardType: TextInputType.numberWithOptions(decimal: decimals),
    textInputAction: textInputAction,
    decoration: InputDecoration(
      labelText: label,
      suffixText: suffix,
      helperText: helper,
      helperMaxLines: 3,
    ),
    validator: (v) {
      final t = (v ?? '').trim();
      if (t.isEmpty) return required ? 'Enter $label' : null;
      final n = double.tryParse(t.replaceAll(',', '.'));
      if (n == null) return 'Enter a number';
      if (min != null && n < min!) return 'At least ${fmtNum(min!)}';
      if (max != null && n > max!) return 'At most ${fmtNum(max!)}';
      return null;
    },
  );
}

double? parseNumber(String text) =>
    double.tryParse(text.trim().replaceAll(',', '.'));
