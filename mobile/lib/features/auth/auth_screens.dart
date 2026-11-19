import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'server_sheet.dart';

class AppMark extends StatelessWidget {
  const AppMark({super.key, this.size = 72});
  final double size;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(size * 0.28),
      ),
      child: Icon(
        Icons.restaurant_menu,
        color: AppColors.onPrimary,
        size: size * 0.5,
      ),
    ),
  );
}

/// Shown while the stored session is checked, or when the server can't be reached.
class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(sessionProvider);
    final unreachable = s.status == AuthStatus.unreachable;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const AppMark(),
                const SizedBox(height: 24),
                if (!unreachable)
                  const CircularProgressIndicator()
                else ...[
                  Text(
                    s.message ?? "Couldn't reach SpotOn.",
                    textAlign: TextAlign.center,
                    style: AppText.body,
                  ),
                  const SizedBox(height: 16),
                  PrimaryButton(
                    label: 'Try again',
                    onPressed: () =>
                        ref.read(sessionProvider.notifier).restore(),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: () => showServerSheet(context),
                    child: const Text('Change server address'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class WelcomeScreen extends ConsumerWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final message = ref.watch(sessionProvider).message;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(),
              const Align(
                alignment: Alignment.centerLeft,
                child: AppMark(size: 80),
              ),
              const SizedBox(height: 24),
              Semantics(
                header: true,
                child: Text('SpotOn', style: AppText.hero),
              ),
              const SizedBox(height: 8),
              Text(
                'Snap a meal. See what\'s left today. Know what to eat next.',
                style: AppText.section.copyWith(
                  fontWeight: FontWeight.w400,
                  color: AppColors.text2,
                ),
              ),
              if (message != null) ...[
                const SizedBox(height: 16),
                InfoBanner(message),
              ],
              const Spacer(),
              PrimaryButton(
                label: 'Get started',
                onPressed: () => context.go('/sign-up'),
              ),
              const SizedBox(height: 4),
              TextButton(
                onPressed: () => context.go('/sign-in'),
                child: const Text('I already have an account'),
              ),
              TextButton(
                onPressed: () => showServerSheet(context),
                child: const Text('Server address'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AuthForm extends ConsumerStatefulWidget {
  const _AuthForm({required this.signUp});
  final bool signUp;

  @override
  ConsumerState<_AuthForm> createState() => _AuthFormState();
}

class _AuthFormState extends ConsumerState<_AuthForm> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _show = false, _busy = false;
  String? _error;

  static const minPassword = 8;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final session = ref.read(sessionProvider.notifier);
    try {
      final email = _email.text.trim();
      if (widget.signUp) {
        await session.signUp(email, _password.text);
      } else {
        await session.signIn(email, _password.text);
      }
      // The router moves on as soon as the session changes.
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final signUp = widget.signUp;
    return Scaffold(
      appBar: AppBar(
        leading: BackButton(onPressed: () => context.go('/welcome')),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
          child: Form(
            key: _form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Semantics(
                  header: true,
                  child: Text(
                    signUp ? 'Create your account' : 'Welcome back',
                    style: AppText.title,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  signUp
                      ? 'SpotOn is for adults (18+). You can export your data any time.'
                      : 'Sign in to pick up where you left off.',
                  style: AppText.caption,
                ),
                const SizedBox(height: 24),
                if (_error != null) ...[
                  InfoBanner(_error!, kind: BannerKind.error),
                  const SizedBox(height: 16),
                ],
                TextFormField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.email],
                  textInputAction: TextInputAction.next,
                  autocorrect: false,
                  decoration: const InputDecoration(labelText: 'Email'),
                  validator: (v) {
                    final t = (v ?? '').trim();
                    return t.contains('@') && t.contains('.')
                        ? null
                        : 'Enter a valid email address';
                  },
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _password,
                  obscureText: !_show,
                  autofillHints: [
                    signUp ? AutofillHints.newPassword : AutofillHints.password,
                  ],
                  textInputAction: TextInputAction.done,
                  onFieldSubmitted: (_) => _submit(),
                  decoration: InputDecoration(
                    labelText: signUp
                        ? 'Password (at least $minPassword characters)'
                        : 'Password',
                    suffixIcon: IconButton(
                      tooltip: _show ? 'Hide password' : 'Show password',
                      icon: Icon(
                        _show
                            ? Icons.visibility_off_outlined
                            : Icons.visibility_outlined,
                      ),
                      onPressed: () => setState(() => _show = !_show),
                    ),
                  ),
                  validator: (v) {
                    final t = v ?? '';
                    if (t.isEmpty) return 'Enter your password';
                    if (signUp && t.length < minPassword) {
                      return 'Use at least $minPassword characters (yours has ${t.length})';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 24),
                PrimaryButton(
                  label: signUp ? 'Create account' : 'Sign in',
                  onPressed: _submit,
                  loading: _busy,
                ),
                const SizedBox(height: 4),
                TextButton(
                  onPressed: () => context.go(signUp ? '/sign-in' : '/sign-up'),
                  child: Text(
                    signUp ? 'I already have an account' : 'Create an account',
                  ),
                ),
                TextButton(
                  onPressed: () => showServerSheet(context),
                  child: const Text('Server address'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class SignUpScreen extends StatelessWidget {
  const SignUpScreen({super.key});
  @override
  Widget build(BuildContext context) => const _AuthForm(signUp: true);
}

class SignInScreen extends StatelessWidget {
  const SignInScreen({super.key});
  @override
  Widget build(BuildContext context) => const _AuthForm(signUp: false);
}
