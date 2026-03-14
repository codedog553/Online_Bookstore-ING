import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import i18n from '../i18n'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/products' },
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/register', component: () => import('../views/Register.vue') },
  { path: '/products', component: () => import('../views/Products.vue') },
  { path: '/products/:id', component: () => import('../views/ProductDetail.vue') },
  { path: '/cart', component: () => import('../views/Cart.vue'), meta: { requiresAuth: true } },
  { path: '/checkout', component: () => import('../views/Checkout.vue'), meta: { requiresAuth: true } },
  { path: '/orders', component: () => import('../views/Orders.vue'), meta: { requiresAuth: true } },
  { path: '/orders/:orderId', component: () => import('../views/OrderDetail.vue'), meta: { requiresAuth: true } },
  { path: '/admin/products', component: () => import('../views/admin/AdminProducts.vue'), meta: { requiresAdmin: true } },
  { path: '/admin/orders', component: () => import('../views/admin/AdminOrders.vue'), meta: { requiresAdmin: true } },
  // 新增：后台评论/报表（后续会补页面文件）
  { path: '/admin/reviews', component: () => import('../views/admin/AdminReviews.vue'), meta: { requiresAdmin: true } },
  { path: '/admin/reports', component: () => import('../views/admin/AdminReports.vue'), meta: { requiresAdmin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const userRaw = localStorage.getItem('user')
  const user = userRaw ? (JSON.parse(userRaw) as { is_admin?: boolean }) : null

  const requiresAuth = Boolean(to.meta?.requiresAuth)
  const requiresAdmin = Boolean(to.meta?.requiresAdmin)

  if (requiresAuth && !token) {
    ElMessage.warning(i18n.global.t('msg.loginRequired'))
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (requiresAdmin) {
    if (!token) {
      ElMessage.warning(i18n.global.t('msg.loginRequired'))
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    if (!user?.is_admin) {
      ElMessage.error(i18n.global.t('msg.noPermission'))
      return { path: '/products' }
    }
  }

  return true
})

export default router
