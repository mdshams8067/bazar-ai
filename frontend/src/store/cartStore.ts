import { create } from 'zustand'
import { addCartItem, clearCart as apiClearCart, deleteCartItem, getCart, updateCartItem } from '../api/cart'
import type { Cart } from '../types/api'

interface CartState {
  cart: Cart | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  addItem: (productId: number, quantity?: number) => Promise<void>
  updateItem: (itemId: number, quantity: number) => Promise<void>
  removeItem: (itemId: number) => Promise<void>
  clear: () => Promise<void>
  /** Bazar Buddy's /chat response already returns the full post-merge
   * cart — sync it directly instead of a redundant extra GET /cart. */
  setCart: (cart: Cart) => void
  reset: () => void
}

export const useCartStore = create<CartState>((set) => ({
  cart: null,
  loading: false,
  error: null,

  async refresh() {
    set({ loading: true, error: null })
    try {
      const cart = await getCart()
      set({ cart, loading: false })
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : 'Could not load cart' })
    }
  },

  // Errors (e.g. "Only 3 in stock") intentionally propagate to the caller
  // so the triggering component can show the message inline.
  async addItem(productId, quantity = 1) {
    const cart = await addCartItem(productId, quantity)
    set({ cart })
  },

  async updateItem(itemId, quantity) {
    const cart = await updateCartItem(itemId, quantity)
    set({ cart })
  },

  async removeItem(itemId) {
    const cart = await deleteCartItem(itemId)
    set({ cart })
  },

  async clear() {
    await apiClearCart()
    set({ cart: { items: [], subtotal_bdt: 0, item_count: 0 } })
  },

  setCart(cart) {
    set({ cart })
  },

  reset() {
    set({ cart: null })
  },
}))
