import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/product.dart';
import '../../providers/products_provider.dart';
import '../../theme/app_colors.dart';
import '../../widgets/common/empty_state.dart';
import '../../widgets/layout/app_header.dart';
import '../../widgets/product/product_card.dart';

class ProductsScreen extends StatefulWidget {
  final String? initialCategory;
  final String? initialSearch;
  const ProductsScreen({super.key, this.initialCategory, this.initialSearch});

  @override
  State<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends State<ProductsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final p = context.read<ProductsProvider>();
      p.loadCategories();
      if (widget.initialCategory != null) p.category = widget.initialCategory;
      if (widget.initialSearch != null) p.search = widget.initialSearch!;
      p.load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ProductsProvider>();

    return Scaffold(
      appBar: const AppHeader(),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: const InputDecoration(hintText: 'Search rice, fish, spices…', isDense: true),
                    onChanged: provider.setSearch,
                  ),
                ),
                const SizedBox(width: 8),
                DropdownButton<SortOption>(
                  value: provider.sort,
                  items: SortOption.values
                      .map((s) => DropdownMenuItem(value: s, child: Text(s.label, style: const TextStyle(fontSize: 12))))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) provider.setSort(v);
                  },
                ),
              ],
            ),
          ),
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: const Text('All products'),
                    selected: provider.category == null,
                    onSelected: (_) => provider.setCategory(null),
                  ),
                ),
                ...provider.categories.map((c) => Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text('${c.category} (${c.count})'),
                        selected: provider.category == c.category,
                        onSelected: (_) => provider.setCategory(c.category),
                      ),
                    )),
              ],
            ),
          ),
          const Divider(height: 1, color: AppColors.line),
          Expanded(
            child: provider.loading
                ? const Center(child: CircularProgressIndicator())
                : provider.items.isEmpty
                    ? EmptyState(
                        title: 'Nothing here yet',
                        subtitle: 'Try a different search term or category — or ask Bazar Buddy, they know the catalog better than any filter.',
                      )
                    : GridView.builder(
                        padding: const EdgeInsets.all(12),
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                          childAspectRatio: 0.68,
                        ),
                        itemCount: provider.items.length,
                        itemBuilder: (context, i) => ProductCard(product: provider.items[i]),
                      ),
          ),
          if (!provider.loading && provider.items.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  TextButton(
                    onPressed: provider.page > 1 ? () => provider.setPage(provider.page - 1) : null,
                    child: const Text('Prev'),
                  ),
                  Text('Page ${provider.page} of ${provider.totalPages}'),
                  TextButton(
                    onPressed: provider.page < provider.totalPages ? () => provider.setPage(provider.page + 1) : null,
                    child: const Text('Next'),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
