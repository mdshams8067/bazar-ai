// Simple emoji icons per category — a placeholder for illustrated category
// iconography (no bespoke asset pipeline for a 3-day build). Keys must
// match the real DB category strings (see GET /products/categories) —
// never hardcode a category *filter value* off this map, it's icons only.
export const CATEGORY_ICONS: Record<string, string> = {
  Rice: '🍚',
  Meat: '🍗',
  Fish: '🐟',
  Spices: '🌶️',
  Dairy: '🥛',
  Eggs: '🥚',
  'Fruits And Vegetables': '🥬',
  'Daal Or Lentil': '🫘',
  Snacks: '🍪',
  Beverages: '🥤',
  Breakfast: '🍳',
  'Candy Chocolate': '🍫',
  'Canned Food': '🥫',
  Frozen: '🧊',
  'Ice Cream': '🍦',
  'Baking Needs': '🧁',
  'Salt And Sugar': '🧂',
  'Ready Mix': '🍲',
  'Sauces And Pickles': '🥫',
  'Soybean Oil': '🫗',
  'Mustard Oil': '🫗',
  'Sunflower Oil': '🫗',
  'Olive Oil': '🫗',
  'Rice Bran Oil': '🫗',
  'Flavored Oil': '🫗',
}

export const DEFAULT_CATEGORY_ICON = '🛒'

// The curated set for the homepage grid, in display order — the "Oils"
// tile links to Soybean Oil (the most common cooking oil here) rather
// than a literal "Oils" filter value, which the backend doesn't recognize.
export const FEATURED_CATEGORIES: { label: string; category: string; icon: string }[] = [
  { label: 'Rice', category: 'Rice', icon: '🍚' },
  { label: 'Meat', category: 'Meat', icon: '🍗' },
  { label: 'Fish', category: 'Fish', icon: '🐟' },
  { label: 'Spices', category: 'Spices', icon: '🌶️' },
  { label: 'Dairy', category: 'Dairy', icon: '🥛' },
  { label: 'Eggs', category: 'Eggs', icon: '🥚' },
  { label: 'Daal', category: 'Daal Or Lentil', icon: '🫘' },
  { label: 'Vegetables', category: 'Fruits And Vegetables', icon: '🥬' },
  { label: 'Oils', category: 'Soybean Oil', icon: '🫗' },
  { label: 'Snacks', category: 'Snacks', icon: '🍪' },
  { label: 'Beverages', category: 'Beverages', icon: '🥤' },
]
