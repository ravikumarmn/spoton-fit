import 'package:material_ui/material_ui.dart';

import '../../core/models.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Edit one food, or add a new one when [item] is null. Values are for ONE unit.
/// Returns the edited item (or null if dismissed). [onRemove] shows a Remove button.
Future<FoodItem?> showItemSheet(
  BuildContext context, {
  FoodItem? item,
  VoidCallback? onRemove,
}) {
  return showAppSheet<FoodItem>(
    context,
    builder: (_) => _ItemSheet(item: item, onRemove: onRemove),
  );
}

class _ItemSheet extends StatefulWidget {
  const _ItemSheet({this.item, this.onRemove});
  final FoodItem? item;
  final VoidCallback? onRemove;

  @override
  State<_ItemSheet> createState() => _ItemSheetState();
}

class _ItemSheetState extends State<_ItemSheet> {
  final _form = GlobalKey<FormState>();
  late final FoodItem _start =
      widget.item?.copy() ??
      FoodItem(
        name: '',
        quantity: 1,
        unit: 'serving',
        perUnit: const Nutrients(),
        source: 'manual',
      );
  late final _name = TextEditingController(text: _start.name);
  late final _unit = TextEditingController(text: _start.unit);
  late final _kcal = TextEditingController(
    text: widget.item == null ? '' : _num(_start.perUnit.kcal),
  );
  late final _protein = TextEditingController(
    text: widget.item == null ? '' : _num(_start.perUnit.protein),
  );
  late final _carbs = TextEditingController(
    text: widget.item == null ? '' : _num(_start.perUnit.carbs),
  );
  late final _fat = TextEditingController(
    text: widget.item == null ? '' : _num(_start.perUnit.fat),
  );
  late String _oil = _start.oilLevel;

  static String _num(double v) =>
      (v * 10).round() % 10 == 0 ? v.round().toString() : v.toStringAsFixed(1);

  @override
  void dispose() {
    for (final c in [_name, _unit, _kcal, _protein, _carbs, _fat]) {
      c.dispose();
    }
    super.dispose();
  }

  void _save() {
    if (!_form.currentState!.validate()) return;
    final out = _start.copy()
      ..name = _name.text.trim()
      ..unit = _unit.text.trim().isEmpty ? 'serving' : _unit.text.trim()
      ..oilLevel = _oil
      ..perUnit = Nutrients(
        kcal: parseNumber(_kcal.text) ?? 0,
        protein: parseNumber(_protein.text) ?? 0,
        carbs: parseNumber(_carbs.text) ?? 0,
        fat: parseNumber(_fat.text) ?? 0,
        fibre: _start.perUnit.fibre,
      );
    Navigator.pop(context, out);
  }

  @override
  Widget build(BuildContext context) {
    final adding = widget.item == null;
    return Form(
      key: _form,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            adding ? 'Add a food' : 'Edit ${_start.name}',
            style: AppText.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          Text(
            'Values are for ONE ${adding ? 'unit' : _start.unit} (one egg, one idli). '
            'SpotOn remembers your values for this food next time.',
            style: AppText.caption,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _name,
            textCapitalization: TextCapitalization.sentences,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(labelText: 'Food'),
            validator: (v) =>
                (v ?? '').trim().isEmpty ? 'Enter the food name' : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _unit,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'One unit is',
              helperText: 'piece, katori, cup, slice, serving…',
            ),
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: NumberField(
                  controller: _kcal,
                  label: 'Calories',
                  suffix: 'kcal',
                  min: 0,
                  max: 5000,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: NumberField(
                  controller: _protein,
                  label: 'Protein',
                  suffix: 'g',
                  min: 0,
                  max: 500,
                  required: false,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: NumberField(
                  controller: _carbs,
                  label: 'Carbs',
                  suffix: 'g',
                  min: 0,
                  max: 1000,
                  required: false,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: NumberField(
                  controller: _fat,
                  label: 'Fat',
                  suffix: 'g',
                  min: 0,
                  max: 500,
                  required: false,
                  textInputAction: TextInputAction.done,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text('How oily is it?', style: AppText.label),
          const SizedBox(height: 4),
          Wrap(
            spacing: 8,
            children: [
              for (final o in const ['none', 'light', 'medium', 'heavy'])
                AppChip(
                  label: o == 'none'
                      ? 'Not oily'
                      : '${o[0].toUpperCase()}${o.substring(1)}',
                  selected: _oil == o,
                  onTap: () => setState(() => _oil = o),
                ),
            ],
          ),
          const SizedBox(height: 16),
          PrimaryButton(
            label: adding ? 'Add food' : 'Save changes',
            onPressed: _save,
          ),
          if (widget.onRemove != null) ...[
            const SizedBox(height: 4),
            TextButton(
              onPressed: () {
                Navigator.pop(context);
                widget.onRemove!();
              },
              style: TextButton.styleFrom(foregroundColor: AppColors.error),
              child: const Text('Remove this food'),
            ),
          ],
        ],
      ),
    );
  }
}
