/// An error from the SpotOn API (its `{"error": {code, message, request_id}}` envelope)
/// or from reaching it. `status == 0` means the request never got an answer.
class ApiException implements Exception {
  const ApiException({
    required this.status,
    required this.code,
    required this.message,
    this.requestId,
  });

  final int status;
  final String code;
  final String message;
  final String? requestId;

  static const networkCode = 'network';
  static const sessionExpiredCode = 'session_expired';

  bool get isNetwork => code == networkCode;
  bool get isSessionExpired => code == sessionExpiredCode;
  bool get isRateLimited => code == 'rate_limited';

  factory ApiException.network() => const ApiException(
    status: 0,
    code: networkCode,
    message: "Couldn't reach SpotOn. Check your connection and the server address, then try again.",
  );

  factory ApiException.sessionExpired() => const ApiException(
    status: 401,
    code: sessionExpiredCode,
    message: 'Your session expired. Please sign in again.',
  );

  @override
  String toString() => 'ApiException($status, $code, $message)';
}
