import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/product.dart';
import '../services/products_service.dart';

class ProductsProvider extends ChangeNotifier {
  final _service = ProductsService();
  Timer? _debounce;

  String? category;
  String search = '';
  SortOption sort = SortOption.relevance;
  int page = 1;
  static const pageSize = 24;

  List<Product> items = [];
  int total = 0;
  bool loading = false;
  String? error;

  List<CategoryCount> categories = [];

  Future<void> loadCategories() async {
    try {
      categories = await _service.listCategories();
      notifyListeners();
    } catch (_) {
      // Non-fatal — sidebar just stays empty.
    }
  }

  Future<void> load() async {
    loading = true;
    notifyListeners();
    try {
      final res = await _service.listProducts(
        category: category,
        search: search,
        sort: sort,
        page: page,
        pageSize: pageSize,
      );
      items = res.items;
      total = res.total;
      error = null;
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  void setCategory(String? value) {
    category = value;
    page = 1;
    load();
  }

  void setSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      search = value;
      page = 1;
      load();
    });
  }

  void setSort(SortOption value) {
    sort = value;
    page = 1;
    load();
  }

  void setPage(int value) {
    page = value;
    load();
  }

  int get totalPages => (total / pageSize).ceil().clamp(1, 1 << 30);

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }
}
