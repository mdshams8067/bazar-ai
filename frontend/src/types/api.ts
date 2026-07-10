// Types mirroring backend/schemas/*.py exactly. Keep in sync with the real
// API — see frontend_build_prompt.md §7 for the source-of-truth contract.

export type ProductUnit = 'kg' | 'gm' | 'ltr' | 'ml' | 'pcs'

export interface Product {
  id: number
  name_en: string
  name_bn: string | null
  category: string
  price_bdt: number
  unit: ProductUnit
  unit_value: number
  stock_qty: number
  image_url: string | null
  in_stock: boolean
}

export interface ProductListResponse {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export interface CategoryCount {
  category: string
  count: number
}

export type SortOption = 'relevance' | 'price_asc' | 'price_desc'

export interface ProductListParams {
  category?: string
  search?: string
  in_stock_only?: boolean
  sort?: SortOption
  page?: number
  page_size?: number
}

// ── Auth ──────────────────────────────────────────────────────────────────

export interface User {
  id: number
  email: string
  name: string
  phone: string | null
  is_active: boolean
  created_at: string
}

export interface Token {
  access_token: string
  token_type: string
}

// ── Cart ──────────────────────────────────────────────────────────────────

export type AddedVia = 'manual' | 'assistant'

export interface CartItem {
  id: number
  product: Product
  quantity: number
  added_via: AddedVia
  substitution_note: string | null
  created_at: string
  line_total_bdt: number
}

export interface Cart {
  items: CartItem[]
  subtotal_bdt: number
  item_count: number
}

// ── Orders ────────────────────────────────────────────────────────────────

export type OrderStatus = 'pending' | 'confirmed' | 'delivered'

export interface OrderItem {
  id: number
  product_id: number | null
  product_name_snapshot: string
  quantity: number
  unit_price_bdt: number
}

export interface Order {
  id: number
  status: OrderStatus
  total_bdt: number
  payment_method: string | null
  created_at: string
  updated_at: string
  items: OrderItem[]
}

export interface OrderListResponse {
  items: Order[]
  total: number
  page: number
  page_size: number
}

// ── Chat (Bazar Buddy) ────────────────────────────────────────────────────

export type ChatIntent =
  | 'cook_dish'
  | 'add_items'
  | 'product_question'
  | 'budget_dish'
  | 'remove_items'
  | 'clear_cart'
  | 'keep_only_items'
  | 'modify_dish'
  | 'other'

export type MatchStatus =
  | 'ok'
  | 'substituted_brand'
  | 'substituted_functional'
  | 'skipped_optional'
  | 'unavailable_essential'
  | 'unmatched'
  | 'error'
  | 'needs_clarification'

export interface IngredientMatch {
  product: Product | null
  status: MatchStatus
  quantity: number
  line_total: number
  note: string | null
  // Only set for status "needs_clarification" — real pack-size options to
  // pick from (e.g. ketchup 250ml/500ml/1kg). Nothing is in the cart yet
  // for this ingredient; picking one adds it directly.
  candidates?: Product[] | null
}

export interface ChatResponse {
  reply: string
  intent: ChatIntent
  matches: IngredientMatch[]
  cart: Cart
  servings: number | null
  // What `servings` counts — "people" normally, "days" etc. if the
  // customer framed the request as a duration/supply instead.
  serving_unit: string
  // Kept separate from `reply` so the UI can render it AFTER the match
  // cards, not folded into the same paragraph before them.
  followup_question: string | null
}
