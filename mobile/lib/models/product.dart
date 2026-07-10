class Product {
  final int id;
  final String nameEn;
  final String? nameBn;
  final String category;
  final double priceBdt;
  final String unit;
  final double unitValue;
  final int stockQty;
  final String? imageUrl;
  final bool inStock;

  Product({
    required this.id,
    required this.nameEn,
    this.nameBn,
    required this.category,
    required this.priceBdt,
    required this.unit,
    required this.unitValue,
    required this.stockQty,
    this.imageUrl,
    required this.inStock,
  });

  factory Product.fromJson(Map<String, dynamic> json) => Product(
        id: json['id'] as int,
        nameEn: json['name_en'] as String,
        nameBn: json['name_bn'] as String?,
        category: json['category'] as String,
        priceBdt: (json['price_bdt'] as num).toDouble(),
        unit: json['unit'] as String,
        unitValue: (json['unit_value'] as num).toDouble(),
        stockQty: json['stock_qty'] as int,
        imageUrl: json['image_url'] as String?,
        inStock: json['in_stock'] as bool,
      );

  String get packLabel {
    final v = unitValue == unitValue.roundToDouble()
        ? unitValue.toInt().toString()
        : unitValue.toString();
    return '$v$unit';
  }
}

class CategoryCount {
  final String category;
  final int count;

  CategoryCount({required this.category, required this.count});

  factory CategoryCount.fromJson(Map<String, dynamic> json) => CategoryCount(
        category: json['category'] as String,
        count: json['count'] as int,
      );
}

enum SortOption { relevance, priceAsc, priceDesc }

extension SortOptionValue on SortOption {
  String get apiValue => switch (this) {
        SortOption.relevance => 'relevance',
        SortOption.priceAsc => 'price_asc',
        SortOption.priceDesc => 'price_desc',
      };

  String get label => switch (this) {
        SortOption.relevance => 'Relevance',
        SortOption.priceAsc => 'Price: low to high',
        SortOption.priceDesc => 'Price: high to low',
      };
}

class ProductListResponse {
  final List<Product> items;
  final int total;
  final int page;
  final int pageSize;

  ProductListResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
  });

  factory ProductListResponse.fromJson(Map<String, dynamic> json) => ProductListResponse(
        items: (json['items'] as List).map((e) => Product.fromJson(e as Map<String, dynamic>)).toList(),
        total: json['total'] as int,
        page: json['page'] as int,
        pageSize: json['page_size'] as int,
      );

  int get totalPages => (total / pageSize).ceil().clamp(1, 1 << 30);
}
