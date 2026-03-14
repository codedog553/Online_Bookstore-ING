import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'
import i18n from '../i18n'

const api = axios.create({
  // 支持通过 Vite env 覆盖后端地址
  // 例如：VITE_API_BASE_URL=http://localhost:8000
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001',
  timeout: 10000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers = config.headers || {}
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (router.currentRoute.value.path !== '/login') {
        ElMessage.warning(i18n.global.t('msg.loginRequired'))
        router.push('/login')
      }
    }
    if (status === 403) {
      ElMessage.error(i18n.global.t('msg.noPermission'))
      const path = router.currentRoute.value.path
      if (path.startsWith('/admin')) {
        router.push('/products')
      }
    }
    return Promise.reject(error)
  }
)

export default api
