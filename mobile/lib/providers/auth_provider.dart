import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/user_profile.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';

enum AuthStatus { idle, loading, ready }

/// Mirrors frontend/src/store/authStore.ts.
class AuthProvider extends ChangeNotifier {
  final _authService = AuthService();
  StreamSubscription<AuthState>? _authSub;

  UserProfile? user;
  AuthStatus status = AuthStatus.idle;
  String? error;

  bool get isAuthenticated => user != null;

  AuthProvider() {
    _authSub = _authService.onAuthStateChange.listen((_) {});
  }

  Future<void> restore() async {
    status = AuthStatus.loading;
    notifyListeners();
    final session = _authService.currentSession;
    if (session == null) {
      user = null;
      status = AuthStatus.ready;
      notifyListeners();
      return;
    }
    try {
      user = await _authService.fetchMe();
    } catch (_) {
      user = null;
    }
    status = AuthStatus.ready;
    notifyListeners();
  }

  Future<void> login(String email, String password) async {
    error = null;
    try {
      await _authService.signIn(email: email, password: password);
      user = await _authService.fetchMe();
      status = AuthStatus.ready;
      notifyListeners();
    } on AuthException catch (e) {
      error = e.message;
      status = AuthStatus.ready;
      notifyListeners();
      rethrow;
    } on ApiError catch (e) {
      error = e.detail;
      status = AuthStatus.ready;
      notifyListeners();
      rethrow;
    }
  }

  Future<void> signup({required String email, required String password, required String name, String? phone}) async {
    error = null;
    try {
      final response = await _authService.signUp(email: email, password: password, name: name, phone: phone);
      if (response.session == null) {
        // Supabase requires email confirmation before a session is issued.
        throw Exception('Check your email to confirm your account, then sign in.');
      }
      user = await _authService.fetchMe();
      status = AuthStatus.ready;
      notifyListeners();
    } on AuthException catch (e) {
      error = e.message;
      status = AuthStatus.ready;
      notifyListeners();
      rethrow;
    } catch (e) {
      status = AuthStatus.ready;
      notifyListeners();
      rethrow;
    }
  }

  Future<void> logout() async {
    await _authService.signOut();
    user = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _authSub?.cancel();
    super.dispose();
  }
}
