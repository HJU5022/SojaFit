import { apiFetch } from './client'

type PricePart = {
  part_number: string | null; manufacturer: string | null
  price_breaks: { quantity: number | null; price: string | null; currency: string | null }[]
  availability: string | null; product_url: string | null
}
export type Prices =
  | { available: true; source: string; fetched_at: string; parts: PricePart[] }
  | { available: false; source: string; reason: string; message: string; parts: [] }

export const fetchPrices = (parts: string[], signal?: AbortSignal) => apiFetch<Prices>(`/api/prices?${new URLSearchParams({ parts: parts.join(',') })}`, { cache: 'no-store', signal })
