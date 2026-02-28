import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/products' },
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/register', component: () => import('../views/Register.vue') },
  { path: '/products', component: () => import('../views/Products.vue') },
  { path: '/products/:id', component: () => import('../views/ProductDetail.vue') },
  { path: '/cart', component: () => import('../views/Cart.vue') },
  { path: '/checkout', component: () => import('../views/Checkout.vue') },
  { path: '/orders', component: () => import('../views/Orders.vue') },
  { path: '/orders/:orderId', component: () => import('../views/OrderDetail.vue') },
  { path: '/admin/products', component: () => import('../views/admin/AdminProducts.vue') },
  { path: '/admin/orders', component: () => import('../views/admin/AdminOrders.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
