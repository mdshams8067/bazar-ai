import 'package:flutter/material.dart';
import '../../models/chat.dart';
import '../../theme/app_colors.dart';
import 'match_card.dart';

class ChatMessageBubble extends StatelessWidget {
  final ChatMessageEntry entry;

  const ChatMessageBubble({super.key, required this.entry});

  @override
  Widget build(BuildContext context) {
    final isUser = entry.isUser;
    final bg = isUser ? AppColors.primary : (entry.isError ? AppColors.warningTint : AppColors.paperWarm);
    final fg = isUser ? Colors.white : AppColors.ink;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(10),
        constraints: const BoxConstraints(maxWidth: 260),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(AppColors.radiusCard)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(entry.text, style: TextStyle(color: fg, fontSize: 14)),
            ...entry.matches.map((m) => MatchCard(match: m)),
            if (entry.followupQuestion != null) ...[
              const SizedBox(height: 6),
              Text(entry.followupQuestion!, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            ],
          ],
        ),
      ),
    );
  }
}
