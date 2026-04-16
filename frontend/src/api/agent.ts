import axios from 'axios'

export const AGENT_API_BASE_URL = (import.meta.env.VITE_AGENT_API_BASE_URL || 'http://localhost:8011').replace(/\/$/, '')

function getPlatformLang(): string {
  const value = String(localStorage.getItem('lang') || '').trim()
  return value || 'zh'
}

const agentApi = axios.create({
  baseURL: AGENT_API_BASE_URL,
  timeout: 40000,
  withCredentials: true,
})

agentApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  const lang = getPlatformLang()
  config.headers = config.headers || {}
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  config.headers['Accept-Language'] = lang
  config.headers['X-User-Lang'] = lang
  return config
})

let csrfToken = ''

export async function ensureAgentCsrfToken() {
  if (csrfToken) return csrfToken
  const { data } = await agentApi.get('/csrf-token')
  csrfToken = data.csrf_token
  return csrfToken
}

agentApi.interceptors.request.use(async (config) => {
  const method = String(config.method || 'get').toUpperCase()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const token = await ensureAgentCsrfToken()
    config.headers = config.headers || {}
    config.headers['X-CSRF-Token'] = token
  }
  return config
})

export interface AgentChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface AgentChatResponse {
  conversation_id: string
  reply: string
  references: Array<{
    product_id: number
    sku_ids: number[]
    title: string
    title_en?: string | null
    author?: string | null
    author_en?: string | null
  }>
  history: AgentChatMessage[]
  action_suggestion?: {
    should_act: boolean
    action: 'none' | 'list' | 'add' | 'update' | 'remove'
    requires_confirmation: boolean
    product_title: string
    sku_id?: number | null
    sku_requests?: Array<{
      sku_id: number
      quantity: number
    }>
    item_id?: number | null
    quantity?: number | null
    user_message: string
    missing_fields?: string[]
      candidate_items?: Array<{
        item_id?: number | null
        sku_id?: number | null
        product_title?: string
        option_summary?: string | null
        quantity?: number | null
      }>
  } | null
}

export interface AgentConfirmationResponse {
  requires_confirmation: boolean
  confirmation_message: string
  confirmation_token: string
  preview: {
    sku_id?: number
    cart_item_id?: number
    product_title: string
    option_summary?: string | null
    quantity?: number | null
  }
  ui?: {
    centered: boolean
    require_manual_action: boolean
    font_size_pt: number
    dialog_width: string
    confirm_label: string
    cancel_label: string
  }
}

export interface AgentCartItem {
  item_id: number
  sku_id: number
  product_id: number
  product_title: string
  option_summary?: string | null
  quantity: number
  is_available: boolean
  stock_quantity?: number | null
}

export interface AgentCartListResponse {
  items: AgentCartItem[]
}

export default agentApi
