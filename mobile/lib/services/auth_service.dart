import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/user_profile.dart';
import 'api_client.dart';

class AuthService {
  final _supabase = Supabase.instance.client;

  Session? get currentSession => _supabase.auth.currentSession;

  Stream<AuthState> get onAuthStateChange => _supabase.auth.onAuthStateChange;

  Future<AuthResponse> signUp({required String email, required String password, required String name, String? phone}) {
    return _supabase.auth.signUp(
      email: email,
      password: password,
      data: {'name': name, if (phone != null && phone.isNotEmpty) 'phone': phone},
    );
  }

  Future<AuthResponse> signIn({required String email, required String password}) {
    return _supabase.auth.signInWithPassword(email: email, password: password);
  }

  Future<void> signOut() => _supabase.auth.signOut();

  Future<UserProfile> fetchMe() {
    return ApiClient.instance.run(
      (dio) => dio.get('/auth/me'),
      (data) => UserProfile.fromJson(data as Map<String, dynamic>),
    );
  }
}
