import '../models/chat.dart';
import 'api_client.dart';

class ChatService {
  Future<ChatResponse> sendMessage(String message, List<Map<String, String>> history) {
    return ApiClient.instance.run(
      (dio) => dio.post('/chat', data: {'message': message, 'history': history}),
      (data) => ChatResponse.fromJson(data as Map<String, dynamic>),
    );
  }
}
