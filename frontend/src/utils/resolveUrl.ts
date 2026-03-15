import { API_BASE_URL } from '../api/http'

/**
 * Resolve a potentially relative backend URL.
 *
 * Backend returns paths like "/uploads/...".
 * If we use them directly in the browser, it will request from frontend origin (5173),
 * so we must prefix with API base URL.
 */
export function resolveBackendUrl(url: string | null | undefined): string {
  const s = (url ?? '').toString().trim()
  if (!s) return ''

  // absolute
  if (/^https?:\/\//i.test(s)) return s

  // root-relative (e.g. /uploads/...)
  if (s.startsWith('/')) return `${API_BASE_URL}${s}`

  // other relative paths: treat as relative to backend root
  return `${API_BASE_URL}/${s}`
}
