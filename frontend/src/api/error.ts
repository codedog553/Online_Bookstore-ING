export function extractErrorMessage(error: any, fallback = '请求失败') {
  try {
    const detail = error?.response?.data?.detail ?? error?.message ?? error?.toString?.()
    if (!detail) return fallback
    if (Array.isArray(detail)) {
      const first = detail[0]
      if (!first) return fallback
      if (typeof first === 'string') return first
      if (first.msg) return first.msg
      if (first.loc && first.msg) return `${first.loc.join('.')}: ${first.msg}`
      return JSON.stringify(first)
    }
    if (typeof detail === 'object') {
      if (detail.message) return detail.message
      if (detail.msg) return detail.msg
      if (detail.error) return detail.error
      return JSON.stringify(detail)
    }
    return String(detail)
  } catch {
    return fallback
  }
}
