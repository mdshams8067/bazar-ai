import 'package:flutter/foundation.dart';

/// Controls the floating Bazar Buddy launcher that's mounted once at the
/// app root (see app.dart) so it's reachable from any screen. A screen that
/// wants it out of the way — the payment WebView (a third-party page) or
/// the chat screen itself — calls hide()/show() in initState/dispose.
/// Counted rather than a bool so overlapping hide() calls (e.g. one screen
/// pushed on top of another that both hid it) can't unhide it too early.
class ChatWidgetProvider extends ChangeNotifier {
  int _hideCount = 0;
  double _bottomInset = 0;

  bool get hidden => _hideCount > 0;
  double get bottomInset => _bottomInset;

  void hide() {
    _hideCount++;
    notifyListeners();
  }

  void show() {
    if (_hideCount > 0) _hideCount--;
    notifyListeners();
  }

  /// Lets a screen with its own sticky bottom bar (e.g. Cart's "Proceed to
  /// checkout") reserve space so the launcher floats above it instead of
  /// covering it.
  void setBottomInset(double value) {
    if (_bottomInset == value) return;
    _bottomInset = value;
    notifyListeners();
  }
}
