import '../models/product.dart';
import 'api_client.dart';

class ProductsService {
  Future<List<CategoryCount>> listCategories() {
    return ApiClient.instance.run(
      (dio) => dio.get('/products/categories'),
      (data) => (data as List).map((e) => CategoryCount.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }

  Future<ProductListResponse> listProducts({
    String? category,
    String? search,
    bool inStockOnly = false,
    SortOption sort = SortOption.relevance,
    int page = 1,
    int pageSize = 24,
  }) {
    return ApiClient.instance.run(
      (dio) => dio.get('/products', queryParameters: {
        if (category != null) 'category': category,
        if (search != null && search.isNotEmpty) 'search': search,
        'in_stock_only': inStockOnly,
        'sort': sort.apiValue,
        'page': page,
        'page_size': pageSize,
      }),
      (data) => ProductListResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  Future<Product> getProduct(int id) {
    return ApiClient.instance.run(
      (dio) => dio.get('/products/$id'),
      (data) => Product.fromJson(data as Map<String, dynamic>),
    );
  }
}
