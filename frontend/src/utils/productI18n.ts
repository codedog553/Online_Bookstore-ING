/**
 * Product i18n helpers (W2).
 *
 * Rules:
 * - If UI language is zh or zh-TW, product information uses Simplified Chinese fields.
 * - Otherwise (en/ja/...), product information uses English fields.
 *
 * Note:
 * UI labels (buttons, table headers...) are still translated by vue-i18n (W1).
 */

export function shouldUseChineseProductText(locale: string): boolean {
  return locale === 'zh' || locale === 'zh-TW'
}

export function pickProductText(
  zh?: string | null,
  en?: string | null,
  locale: string = 'zh'
): string {
  const useZh = shouldUseChineseProductText(String(locale))
  if (useZh) return (zh || en || '').toString()
  return (en || zh || '').toString()
}

/**
 * Translate common book version values to English.
 *
 * This is a fallback when vendor does not provide a full optionValueI18n mapping.
 */
export function fallbackVersionToEnglish(value: string): string {
  if (value === '平装') return 'Paperback'
  if (value === '精装') return 'Hardcover'
  return value
}

function safeJsonParseObject(s: any): Record<string, any> {
  const raw = (s ?? '').toString().trim()
  if (!raw) return {}
  try {
    const v = JSON.parse(raw)
    return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, any>) : {}
  } catch {
    return {}
  }
}

export function getOptionValueI18n(productOptionsJson?: string | null): Record<string, Record<string, string>> {
  const obj = safeJsonParseObject(productOptionsJson)
  const m = obj?.optionValueI18n
  if (m && typeof m === 'object' && !Array.isArray(m)) return m as Record<string, Record<string, string>>
  return {}
}

export function translateOptionValue(
  optionKey: string,
  value: string,
  productOptionsJson: string | null | undefined,
  locale: string
): string {
  // W2: zh/zh-TW use Chinese product fields (options usually stored in Chinese)
  if (shouldUseChineseProductText(locale)) return value

  const i18nMap = getOptionValueI18n(productOptionsJson)
  const perKey = i18nMap?.[optionKey] || i18nMap?.[optionKey?.toLowerCase?.() as any]
  if (perKey && perKey[value]) return String(perKey[value])

  // Fallback: common "version" values are stored in Chinese
  const k = (optionKey || '').toLowerCase()
  if (k.includes('version') || optionKey === '版本') return fallbackVersionToEnglish(value)

  return value
}

/**
 * Format option_values JSON (SKU snapshot) to display text.
 *
 * - locale zh/zh-TW: display raw values.
 * - other locale: translate values using product.options.optionValueI18n if available.
 */
export function formatOptionValues(
  optionValuesJson: string,
  productOptionsJson: string | null | undefined,
  locale: string,
  keyLabel?: (key: string) => string
): string {
  const ov = safeJsonParseObject(optionValuesJson)
  const entries = Object.entries(ov)
  if (!entries.length) return optionValuesJson

  return entries
    .map(([k, v]) => {
      const label = keyLabel ? keyLabel(k) : k
      const value = translateOptionValue(k, String(v), productOptionsJson, locale)
      return `${label}：${value}`
    })
    .join(', ')
}
