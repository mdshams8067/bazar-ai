import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';
import '../../models/chat.dart';
import '../../providers/auth_provider.dart';
import '../../providers/cart_provider.dart';
import '../../providers/chat_widget_provider.dart';
import '../../routes/app_router.dart';
import '../../services/chat_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/chat/chat_message_bubble.dart';
import '../../widgets/chat/typing_indicator.dart';

const _maxHistoryMessages = 6;
const _uuid = Uuid();

/// A full screen rather than a floating panel — a fixed-size overlay sat
/// outside any Scaffold, so the keyboard covered it instead of resizing
/// around it. A real Scaffold gets keyboard-avoidance for free, and gives
/// match cards/pack-size pickers room to actually be readable.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _chatService = ChatService();
  final _inputCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  ChatWidgetProvider? _chatVisibility;

  final List<ChatMessageEntry> _messages = [
    ChatMessageEntry(
      id: 'welcome',
      isUser: false,
      text: "Hi, I'm Bazar Buddy! Tell me what you're cooking — \"morog polao for 6\" or \"biryani under 1500 taka\" — "
          "and I'll fill your cart with what's in stock.",
    ),
  ];

  bool _isSending = false;
  String? _lastIntent;
  String _lastServingUnit = 'people';

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _chatVisibility ??= context.read<ChatWidgetProvider>()..hide();
  }

  @override
  void dispose() {
    _chatVisibility?.show();
    _inputCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  List<Map<String, String>> _toHistory() {
    final relevant = _messages.where((m) => m.id != 'welcome' && !m.isError).toList();
    final last = relevant.length > _maxHistoryMessages ? relevant.sublist(relevant.length - _maxHistoryMessages) : relevant;
    return last.map((m) {
      final text = m.followupQuestion != null ? '${m.text} ${m.followupQuestion}' : m.text;
      return {'role': m.isUser ? 'user' : 'assistant', 'text': text};
    }).toList();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(_scrollCtrl.position.maxScrollExtent, duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  Future<void> _send(String text) async {
    if (text.trim().isEmpty || _isSending) return;
    final history = _toHistory();
    setState(() {
      _messages.add(ChatMessageEntry(id: _uuid.v4(), isUser: true, text: text));
      _isSending = true;
    });
    _inputCtrl.clear();
    _scrollToBottom();

    try {
      final res = await _chatService.sendMessage(text, history);
      setState(() {
        _messages.add(ChatMessageEntry(
          id: _uuid.v4(),
          isUser: false,
          text: res.reply,
          matches: res.matches,
          followupQuestion: res.followupQuestion,
        ));
        _lastIntent = res.intent;
        _lastServingUnit = res.servingUnit;
      });
      if (mounted) context.read<CartProvider>().setCart(res.cart);
    } catch (e) {
      setState(() {
        _messages.add(ChatMessageEntry(id: _uuid.v4(), isUser: false, text: e.toString(), isError: true));
      });
    } finally {
      if (mounted) setState(() => _isSending = false);
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final showQuickReplies = !_isSending && (_lastIntent == 'cook_dish' || _lastIntent == 'budget_dish');

    return Scaffold(
      // White, not the app's usual paperWarm page background — assistant
      // bubbles are paperWarm themselves (matching the web app's chat
      // panel), so without this contrast they'd be invisible.
      backgroundColor: AppColors.paper,
      appBar: AppBar(title: const Text('Bazar Buddy')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: ListView.builder(
                  controller: _scrollCtrl,
                  itemCount: _messages.length + (_isSending ? 1 : 0),
                  itemBuilder: (context, i) {
                    if (i == _messages.length) {
                      return const Align(alignment: Alignment.centerLeft, child: Padding(padding: EdgeInsets.symmetric(vertical: 4), child: TypingIndicator()));
                    }
                    return ChatMessageBubble(entry: _messages[i]);
                  },
                ),
              ),
              if (showQuickReplies)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Wrap(
                    spacing: 6,
                    children: [2, 4, 6, 8].map((n) {
                      return OutlinedButton(
                        onPressed: () => _send('make it enough for $n $_lastServingUnit'),
                        style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4)),
                        child: Text('$n $_lastServingUnit', style: const TextStyle(fontSize: 12)),
                      );
                    }).toList(),
                  ),
                ),
              if (auth.isAuthenticated)
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _inputCtrl,
                        enabled: !_isSending,
                        decoration: const InputDecoration(hintText: 'Ask Bazar Buddy…', isDense: true),
                        onSubmitted: _send,
                      ),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton(
                      onPressed: _isSending ? null : () => _send(_inputCtrl.text),
                      child: const Text('Send'),
                    ),
                  ],
                )
              else
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Column(
                    children: [
                      const Text('Sign in to start shopping with Bazar Buddy.', textAlign: TextAlign.center),
                      TextButton(
                        onPressed: () => context.push('/login?redirect=${Uri.encodeComponent('/chat')}'),
                        child: const Text('Sign in'),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class ChatLauncherButton extends StatelessWidget {
  const ChatLauncherButton({super.key});

  @override
  Widget build(BuildContext context) {
    final inset = context.watch<ChatWidgetProvider>().bottomInset;
    return Positioned(
      right: 16,
      bottom: 16 + inset,
      child: FloatingActionButton(
        backgroundColor: AppColors.primary,
        onPressed: () => rootNavigatorKey.currentContext?.push('/chat'),
        child: const Text('💬', style: TextStyle(fontSize: 22)),
      ),
    );
  }
}
