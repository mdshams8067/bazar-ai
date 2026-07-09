import { apiRequest, buildQuery } from './client'
import type { CategoryCount, Product, ProductListParams, ProductListResponse } from '../types/api'

export function listProducts(params: ProductListParams = {}): Promise<ProductListResponse> {
  const query = buildQuery({
    category: params.category,
    search: params.search,
    in_stock_only: params.in_stock_only,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  })
  return apiRequest<ProductListResponse>(`/products${query}`)
}

export function getProduct(id: number): Promise<Product> {
  return apiRequest<Product>(`/products/${id}`)
}

export function listCategories(): Promise<CategoryCount[]> {
  return apiRequest<CategoryCount[]>('/products/categories')
}
