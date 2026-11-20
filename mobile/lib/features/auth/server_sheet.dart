import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/providers.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Where the SpotOn server is. Needed until the app talks to a hosted server.
Future<void> showServerSheet(BuildContext context) =>
    showAppSheet<void>(context, builder: (_) => const _ServerSheet());

class _ServerSheet extends ConsumerStatefulWidget {
  const _ServerSheet();

  @override
  ConsumerState<_ServerSheet> createState() => _ServerSheetState();
}

class _ServerSheetState extends ConsumerState<_ServerSheet> {
  late final TextEditingController _url = TextEditingController(
    text: ref.read(serverUrlProvider),
  );
  String? _result;
  bool _ok = false, _busy = false;

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Future<void> _save({bool test = false}) async {
    setState(() {
      _busy = true;
      _result = null;
    });
    await ref.read(serverUrlProvider.notifier).set(_url.text);
    if (test) {
      try {
        await ref.read(apiProvider).ping();
        _ok = true;
        _result = 'Connected ✓';
      } catch (e) {
        _ok = false;
        _result = errorMessage(e);
      }
    }
    if (!mounted) return;
    setState(() => _busy = false);
    if (!test) {
      Navigator.pop(context);
      await ref.read(sessionProvider.notifier).restore();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Server address', style: AppText.title),
        const SizedBox(height: 8),
        Text(
          'The address of your SpotOn server. Android emulator: http://10.0.2.2:8000. '
          "A real phone on the same Wi-Fi: your computer's address, like http://192.168.1.20:8000.",
          style: AppText.caption,
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _url,
          keyboardType: TextInputType.url,
          autocorrect: false,
          decoration: const InputDecoration(labelText: 'Server address'),
        ),
        if (_result != null) ...[
          const SizedBox(height: 12),
          InfoBanner(
            _result!,
            kind: _ok ? BannerKind.soft : BannerKind.error,
            icon: _ok ? Symbols.check_circle_rounded : null,
          ),
        ],
        const SizedBox(height: 16),
        SecondaryButton(
          label: 'Test connection',
          onPressed: _busy ? null : () => _save(test: true),
        ),
        const SizedBox(height: 8),
        PrimaryButton(
          label: 'Save',
          onPressed: _busy ? null : _save,
          loading: _busy,
        ),
      ],
    );
  }
}
