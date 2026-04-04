import { defineStore } from 'pinia'
import api from '../api/http'

export interface User {
  id: number
  full_name: string
  email: string
  language?: string
  is_admin: boolean
  default_address_id?: number | null
}

export const useAuthStore = defineStore('auth', {
  state: (): { token: string; user: User | null } => ({
    token: localStorage.getItem('token') || '',
    user: (localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user') as string) : null) as User | null,
  }),
  actions: {
    async login(email: string, password: string) {
      const { data } = await api.post('/api/auth/login', { email, password })
      this.token = data.access_token
      localStorage.setItem('token', this.token)
      await this.fetchMe()
    },
    async register(
      full_name: string,
      email: string,
      password: string,
      shipping_address: {
        receiver_name: string
        phone?: string
        province: string
        city: string
        district: string
        detail_address: string
      }
    ) {
      const { data } = await api.post('/api/auth/register', { full_name, email, password, shipping_address })
      this.token = data.access_token
      localStorage.setItem('token', this.token)
      await this.fetchMe()
    },
    async fetchMe() {
      const { data } = await api.get('/api/users/me')
      this.user = data
      localStorage.setItem('user', JSON.stringify(data))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
    tryRestore() {
      if (this.token && !this.user) {
        this.fetchMe().catch(() => this.logout())
      }
    }
  }
})
