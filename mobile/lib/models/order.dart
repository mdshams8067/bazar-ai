enum OrderStatus { pending, confirmed, delivered }

OrderStatus orderStatusFromJson(String v) => switch (v) {
      'confirmed' => OrderStatus.confirmed,
      'delivered' => OrderStatus.delivered,
      _ => OrderStatus.pending,
    };

extension OrderStatusValue on OrderStatus {
  String get apiValue => switch (this) {
        OrderStatus.pending => 'pending',
        OrderStatus.confirmed => 'confirmed',
        OrderStatus.delivered => 'delivered',
      };

  String get label => switch (this) {
        OrderStatus.pending => 'Pending',
        OrderStatus.confirmed => 'Confirmed',
        OrderStatus.delivered => 'Delivered',
      };

  /// Mirrors NEXT_ORDER_STATUS from the web app — one step at a time,
  /// null once delivered (no next step).
  OrderStatus? get next => switch (this) {
        OrderStatus.pending => OrderStatus.confirmed,
        OrderStatus.confirmed => OrderStatus.delivered,
        OrderStatus.delivered => null,
      };
}

class OrderItem {
  final int id;
  final int? productId;
  final String productNameSnapshot;
  final int quantity;
  final double unitPriceBdt;

  OrderItem({
    required this.id,
    this.productId,
    required this.productNameSnapshot,
    required this.quantity,
    required this.unitPriceBdt,
  });

  factory OrderItem.fromJson(Map<String, dynamic> json) => OrderItem(
        id: json['id'] as int,
        productId: json['product_id'] as int?,
        productNameSnapshot: json['product_name_snapshot'] as String,
        quantity: json['quantity'] as int,
        unitPriceBdt: (json['unit_price_bdt'] as num).toDouble(),
      );

  double get lineTotal => unitPriceBdt * quantity;
}

class Order {
  final int id;
  final OrderStatus status;
  final double totalBdt;
  final String? paymentMethod;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<OrderItem> items;

  Order({
    required this.id,
    required this.status,
    required this.totalBdt,
    this.paymentMethod,
    required this.createdAt,
    required this.updatedAt,
    required this.items,
  });

  factory Order.fromJson(Map<String, dynamic> json) => Order(
        id: json['id'] as int,
        status: orderStatusFromJson(json['status'] as String),
        totalBdt: (json['total_bdt'] as num).toDouble(),
        paymentMethod: json['payment_method'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
        items: (json['items'] as List).map((e) => OrderItem.fromJson(e as Map<String, dynamic>)).toList(),
      );
}

class OrderListResponse {
  final List<Order> items;
  final int total;
  final int page;
  final int pageSize;

  OrderListResponse({required this.items, required this.total, required this.page, required this.pageSize});

  factory OrderListResponse.fromJson(Map<String, dynamic> json) => OrderListResponse(
        items: (json['items'] as List).map((e) => Order.fromJson(e as Map<String, dynamic>)).toList(),
        total: json['total'] as int,
        page: json['page'] as int,
        pageSize: json['page_size'] as int,
      );
}
