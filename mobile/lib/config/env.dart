import 'package:flutter_dotenv/flutter_dotenv.dart';

class Env {
  Env._();

  static String get apiBaseUrl => dotenv.get('API_BASE_URL');
  static String get supabaseUrl => dotenv.get('SUPABASE_URL');
  static String get supabaseAnonKey => dotenv.get('SUPABASE_ANON_KEY');
}
