import { apiRequest } from './client'

// Starts a real SSLCommerz (sandbox) payment session for an already-created,
// still-pending order; returns their hosted checkout page URL to redirect
// the browser to — SSLCommerz's page can't be embedded/rendered by us.
export function initSslcommerzPayment(orderId: number): Promise<{ gateway_url: string }> {
  return apiRequest<{ gateway_url: string }>(`/payment/sslcommerz/init/${orderId}`, { method: 'POST' })
}
