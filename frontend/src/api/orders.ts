import { apiRequest, buildQuery } from './client'
import type { Order, OrderListResponse, OrderStatus } from '../types/api'

// Omitting paymentMethod means "pay via SSLCommerz" — the caller follows
// up with a separate initSslcommerzPayment() call. "cod" needs no gateway
// at all, so it's recorded directly on the order at creation.
export function createOrder(paymentMethod?: 'cod'): Promise<Order> {
  return apiRequest<Order>('/orders', {
    method: 'POST',
    body: paymentMethod ? { payment_method: paymentMethod } : undefined,
  })
}

export function listOrders(page = 1, pageSize = 20): Promise<OrderListResponse> {
  return apiRequest<OrderListResponse>(`/orders${buildQuery({ page, page_size: pageSize })}`)
}

export function getOrder(id: number): Promise<Order> {
  return apiRequest<Order>(`/orders/${id}`)
}

// Advances exactly one step (pending -> confirmed -> delivered); the
// backend 400s if you try to skip a step.
export function advanceOrderStatus(id: number, status: OrderStatus): Promise<Order> {
  return apiRequest<Order>(`/orders/${id}/status`, { method: 'PATCH', body: { status } })
}

export const NEXT_ORDER_STATUS: Partial<Record<OrderStatus, OrderStatus>> = {
  pending: 'confirmed',
  confirmed: 'delivered',
}
