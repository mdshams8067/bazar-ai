import { apiRequest } from './client'
import type { AddedVia, Cart } from '../types/api'

export function getCart(): Promise<Cart> {
  return apiRequest<Cart>('/cart')
}

export function addCartItem(
  productId: number,
  quantity = 1,
  addedVia: AddedVia = 'manual',
): Promise<Cart> {
  return apiRequest<Cart>('/cart/items', {
    method: 'POST',
    body: { product_id: productId, quantity, added_via: addedVia },
  })
}

export function updateCartItem(itemId: number, quantity: number): Promise<Cart> {
  // quantity <= 0 deletes the row — documented backend behavior.
  return apiRequest<Cart>(`/cart/items/${itemId}`, { method: 'PATCH', body: { quantity } })
}

export function deleteCartItem(itemId: number): Promise<Cart> {
  return apiRequest<Cart>(`/cart/items/${itemId}`, { method: 'DELETE' })
}

export function clearCart(): Promise<void> {
  return apiRequest<void>('/cart', { method: 'DELETE' })
}
