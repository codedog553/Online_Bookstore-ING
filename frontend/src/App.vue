<template>
  <div>
    <header class="app-header">
      <router-link to="/products" class="logo">📚 在线书店</router-link>
      <div class="spacer" />
      <el-input v-model="keyword" placeholder="搜索书名" size="small" style="max-width: 260px" @keyup.enter="doSearch" />
      <el-button size="small" type="primary" class="ml8" @click="doSearch">搜索</el-button>
      <router-link to="/cart" class="ml16">
        <el-button size="small">购物车</el-button>
      </router-link>
      <template v-if="isAuthed">
        <el-dropdown class="ml8">
          <span class="el-dropdown-link">
            {{ user?.full_name || '用户' }}
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="goOrders">我的订单</el-dropdown-item>
              <el-dropdown-item v-if="user?.is_admin" @click="goAdminProducts">后台-商品</el-dropdown-item>
              <el-dropdown-item v-if="user?.is_admin" @click="goAdminOrders">后台-订单</el-dropdown-item>
              <el-dropdown-item divided @click="logout">退出</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <router-link to="/login" class="ml8">
          <el-button size="small">登录</el-button>
        </router-link>
        <router-link to="/register" class="ml8">
          <el-button size="small">注册</el-button>
        </router-link>
      </template>
    </header>

    <main class="app-main">
      <router-view />
    </main>

    <footer class="app-footer">© 2026 在线书店 Demo</footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './store/auth'

const router = useRouter()
const auth = useAuthStore()
const keyword = ref('')

const isAuthed = computed(() => !!auth.token)
const user = computed(() => auth.user)

function doSearch() {
  router.push({ path: '/products', query: { keyword: keyword.value } })
}

function logout() {
  auth.logout()
  router.push('/login')
}
function goOrders() { router.push('/orders') }
function goAdminProducts() { router.push('/admin/products') }
function goAdminOrders() { router.push('/admin/orders') }

onMounted(() => {
  auth.tryRestore()
})
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #eee;
  gap: 8px;
}
.logo { font-weight: 600; text-decoration: none; color: #333; }
.spacer { flex: 1; }
.ml8 { margin-left: 8px; }
.ml16 { margin-left: 16px; }
.app-main { padding: 16px; min-height: calc(100vh - 120px); }
.app-footer { text-align: center; padding: 12px; color: #666; border-top: 1px solid #eee; }
</style>
