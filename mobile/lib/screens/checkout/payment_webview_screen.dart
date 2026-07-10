import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

/// The backend's SSLCommerz success/fail/cancel callbacks 303-redirect to
/// `{FRONTEND_URL}/order-confirmation/{id}?payment=...` — a web URL, since
/// no mobile deep link is wired up server-side (no backend changes in
/// scope). We detect completion by matching the WebView's navigation
/// requests on path+query only (robust to whatever host FRONTEND_URL is),
/// then prevent the actual web page from loading (it has its own session
/// model we don't share) and pop back to the native confirmation screen.
class PaymentWebViewScreen extends StatefulWidget {
  final String gatewayUrl;
  final int orderId;

  const PaymentWebViewScreen({super.key, required this.gatewayUrl, required this.orderId});

  @override
  State<PaymentWebViewScreen> createState() => _PaymentWebViewScreenState();
}

class _PaymentWebViewScreenState extends State<PaymentWebViewScreen> {
  late final WebViewController _controller;
  double _progress = 0;
  bool _resolved = false;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(NavigationDelegate(
        onProgress: (p) => setState(() => _progress = p / 100),
        onNavigationRequest: (request) => _handleUrl(request.url) ? NavigationDecision.prevent : NavigationDecision.navigate,
        onPageFinished: (url) => _handleUrl(url),
      ))
      ..loadRequest(Uri.parse(widget.gatewayUrl));
  }

  bool _handleUrl(String url) {
    if (_resolved) return true;
    final uri = Uri.tryParse(url);
    if (uri == null) return false;
    if (!uri.path.contains('/order-confirmation/${widget.orderId}')) return false;

    _resolved = true;
    final payment = uri.queryParameters['payment'] ?? 'success';
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) Navigator.of(context).pop(payment);
    });
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Payment'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop('cancelled'),
            child: const Text('Cancel', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_progress < 1) LinearProgressIndicator(value: _progress),
          Expanded(child: WebViewWidget(controller: _controller)),
        ],
      ),
    );
  }
}
