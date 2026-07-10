import 'package:flutter/foundation.dart';

/// Mirrors frontend/src/store/chatWidgetStore.ts — purely an open/closed flag.
class ChatWidgetProvider extends ChangeNotifier {
  bool isOpen = false;

  void open() {
    isOpen = true;
    notifyListeners();
  }

  void close() {
    isOpen = false;
    notifyListeners();
  }

  void toggle() {
    isOpen = !isOpen;
    notifyListeners();
  }
}
