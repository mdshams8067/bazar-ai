import 'cart.dart';
import 'product.dart';

enum MatchStatus {
  ok,
  substitutedBrand,
  substitutedFunctional,
  substitutedDiy,
  skippedOptional,
  unavailableEssential,
  unmatched,
  error,
  needsClarification,
}

MatchStatus matchStatusFromJson(String v) => switch (v) {
      'ok' => MatchStatus.ok,
      'substituted_brand' => MatchStatus.substitutedBrand,
      'substituted_functional' => MatchStatus.substitutedFunctional,
      'substituted_diy' => MatchStatus.substitutedDiy,
      'skipped_optional' => MatchStatus.skippedOptional,
      'unavailable_essential' => MatchStatus.unavailableEssential,
      'unmatched' => MatchStatus.unmatched,
      'needs_clarification' => MatchStatus.needsClarification,
      _ => MatchStatus.error,
    };

/// One real product matched for a DIY substitute component — see
/// IngredientMatch.components (only set for status substitutedDiy).
class MatchComponent {
  final Product product;
  final double quantity;
  final double lineTotal;

  MatchComponent({required this.product, required this.quantity, required this.lineTotal});

  factory MatchComponent.fromJson(Map<String, dynamic> json) => MatchComponent(
        product: Product.fromJson(json['product'] as Map<String, dynamic>),
        quantity: (json['quantity'] as num).toDouble(),
        lineTotal: (json['line_total'] as num).toDouble(),
      );
}

class IngredientMatch {
  final Product? product;
  final MatchStatus status;
  final double quantity;
  final double lineTotal;
  final String? note;
  final List<Product>? candidates;
  final List<MatchComponent>? components;

  IngredientMatch({
    this.product,
    required this.status,
    required this.quantity,
    required this.lineTotal,
    this.note,
    this.candidates,
    this.components,
  });

  factory IngredientMatch.fromJson(Map<String, dynamic> json) => IngredientMatch(
        product: json['product'] != null ? Product.fromJson(json['product'] as Map<String, dynamic>) : null,
        status: matchStatusFromJson(json['status'] as String),
        quantity: (json['quantity'] as num).toDouble(),
        lineTotal: (json['line_total'] as num).toDouble(),
        note: json['note'] as String?,
        candidates: json['candidates'] != null
            ? (json['candidates'] as List).map((e) => Product.fromJson(e as Map<String, dynamic>)).toList()
            : null,
        components: json['components'] != null
            ? (json['components'] as List).map((e) => MatchComponent.fromJson(e as Map<String, dynamic>)).toList()
            : null,
      );
}

class ChatResponse {
  final String reply;
  final String intent;
  final List<IngredientMatch> matches;
  final Cart cart;
  final double? servings;
  final String servingUnit;
  final String? followupQuestion;

  ChatResponse({
    required this.reply,
    required this.intent,
    required this.matches,
    required this.cart,
    this.servings,
    required this.servingUnit,
    this.followupQuestion,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) => ChatResponse(
        reply: json['reply'] as String,
        intent: json['intent'] as String,
        matches: (json['matches'] as List).map((e) => IngredientMatch.fromJson(e as Map<String, dynamic>)).toList(),
        cart: Cart.fromJson(json['cart'] as Map<String, dynamic>),
        servings: (json['servings'] as num?)?.toDouble(),
        servingUnit: json['serving_unit'] as String? ?? 'people',
        followupQuestion: json['followup_question'] as String?,
      );
}

/// One entry in the chat panel's local scrollback (not a wire type).
class ChatMessageEntry {
  final String id;
  final bool isUser;
  final String text;
  final List<IngredientMatch> matches;
  final String? followupQuestion;
  final bool isError;

  ChatMessageEntry({
    required this.id,
    required this.isUser,
    required this.text,
    this.matches = const [],
    this.followupQuestion,
    this.isError = false,
  });
}
