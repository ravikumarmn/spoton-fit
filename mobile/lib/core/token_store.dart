import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

/// Where the login tokens live. The real one uses the iOS Keychain / Android Keystore.
abstract interface class TokenStore {
  Future<AuthTokens?> read();
  Future<void> write(AuthTokens tokens);
  Future<void> clear();
}

class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;
  static const _access = 'spoton.access_token';
  static const _refresh = 'spoton.refresh_token';

  @override
  Future<AuthTokens?> read() async {
    final a = await _storage.read(key: _access);
    final r = await _storage.read(key: _refresh);
    return (a == null || r == null)
        ? null
        : AuthTokens(accessToken: a, refreshToken: r);
  }

  @override
  Future<void> write(AuthTokens t) async {
    await _storage.write(key: _access, value: t.accessToken);
    await _storage.write(key: _refresh, value: t.refreshToken);
  }

  @override
  Future<void> clear() async {
    await _storage.delete(key: _access);
    await _storage.delete(key: _refresh);
  }
}

class MemoryTokenStore implements TokenStore {
  AuthTokens? _tokens;

  @override
  Future<AuthTokens?> read() async => _tokens;

  @override
  Future<void> write(AuthTokens tokens) async => _tokens = tokens;

  @override
  Future<void> clear() async => _tokens = null;
}
