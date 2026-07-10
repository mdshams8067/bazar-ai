import 'product.dart';

enum AddedVia { manual, assistant }

AddedVia addedViaFromJson(String v) => v == 'assistant' ? AddedVia.assistant : AddedVia.manual;

class CartItem {
  final int id;
  final Product product;
  final int quantity;
  final AddedVia addedVia;
  final String? substitutionNote;
  final DateTime createdAt;
  final double lineTotalBdt;

  CartItem({
    required this.id,
    required this.product,
    required this.quantity,
    required this.addedVia,
    this.substitutionNote,
    required this.createdAt,
    required this.lineTotalBdt,
  });

  factory CartItem.fromJson(Map<String, dynamic> json) => CartItem(
        id: json['id'] as int,
        product: Product.fromJson(json['product'] as Map<String, dynamic>),
        quantity: json['quantity'] as int,
        addedVia: addedViaFromJson(json['added_via'] as String),
        substitutionNote: json['substitution_note'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        lineTotalBdt: (json['line_total_bdt'] as num).toDouble(),
      );
}

class Cart {
  final List<CartItem> items;
  final double subtotalBdt;
  final int itemCount;

  Cart({required this.items, required this.subtotalBdt, required this.itemCount});

  factory Cart.fromJson(Map<String, dynamic> json) => Cart(
        items: (json['items'] as List).map((e) => CartItem.fromJson(e as Map<String, dynamic>)).toList(),
        subtotalBdt: (json['subtotal_bdt'] as num).toDouble(),
        itemCount: json['item_count'] as int,
      );

  static Cart empty() => Cart(items: [], subtotalBdt: 0, itemCount: 0);
}
