import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../theme/app_colors.dart';

const categoryIcons = <String, String>{
  'Rice': '🍚',
  'Meat': '🍗',
  'Fish': '🐟',
  'Spices': '🌶️',
  'Dairy': '🥛',
  'Eggs': '🥚',
  'Daal Or Lentil': '🫘',
  'Fruits And Vegetables': '🥬',
  'Oils': '🫗',
  'Snacks': '🍪',
  'Beverages': '🥤',
};

class CategoryGrid extends StatelessWidget {
  const CategoryGrid({super.key});

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 4,
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 0.9,
      ),
      itemCount: categoryIcons.length,
      itemBuilder: (context, i) {
        final entry = categoryIcons.entries.elementAt(i);
        return InkWell(
          onTap: () => context.push('/products?category=${Uri.encodeComponent(entry.key)}'),
          child: Container(
            decoration: BoxDecoration(
              color: AppColors.paper,
              border: Border.all(color: AppColors.line),
              borderRadius: BorderRadius.circular(AppColors.radiusCard),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(entry.value, style: const TextStyle(fontSize: 24)),
                const SizedBox(height: 4),
                Text(entry.key.split(' ').first, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
        );
      },
    );
  }
}
