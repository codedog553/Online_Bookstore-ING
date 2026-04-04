<template>
  <div>
    <header class="app-header">
      <router-link to="/products" class="logo">📚 {{ t('app.title') }}</router-link>
      <div class="spacer" />
      <el-input
        v-model="keyword"
        :placeholder="t('app.searchPlaceholder')"
        size="small"
        style="max-width: 260px"
        @keyup.enter="doSearch"
      />
      <el-button size="small" type="primary" class="ml8" @click="doSearch">{{ t('app.search') }}</el-button>

      <el-dropdown class="ml8">
        <span class="el-dropdown-link">{{ t('app.language') }}: {{ currentLangLabel }}</span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="setLang('zh')">{{ t('lang.zh') }}</el-dropdown-item>
            <el-dropdown-item @click="setLang('zh-TW')">{{ t('lang.zhTW') }}</el-dropdown-item>
            <el-dropdown-item @click="setLang('en')">{{ t('lang.en') }}</el-dropdown-item>
            <el-dropdown-item @click="setLang('ja')">{{ t('lang.ja') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <router-link to="/cart" class="ml16">
        <el-button size="small">{{ t('app.cart') }}</el-button>
      </router-link>
      <template v-if="isAuthed">
        <el-dropdown class="ml8">
          <span class="el-dropdown-link">
            {{ user?.full_name || t('app.user') }}
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="goOrders">{{ t('app.myOrders') }}</el-dropdown-item>
              <el-dropdown-item v-if="user?.is_admin" @click="goAdminProducts">{{ t('app.adminProducts') }}</el-dropdown-item>
              <el-dropdown-item v-if="user?.is_admin" @click="goAdminOrders">{{ t('app.adminOrders') }}</el-dropdown-item>
              <el-dropdown-item v-if="user?.is_admin" @click="goAdminReviews">{{ t('app.adminReviews') }}</el-dropdown-item>
              <el-dropdown-item v-if="user?.is_admin" @click="goAdminReports">{{ t('app.adminReports') }}</el-dropdown-item>
              <el-dropdown-item divided @click="logout">{{ t('app.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <router-link to="/login" class="ml8">
          <el-button size="small">{{ t('app.login') }}</el-button>
        </router-link>
        <router-link to="/register" class="ml8">
          <el-button size="small">{{ t('app.register') }}</el-button>
        </router-link>
      </template>
    </header>

    <main class="app-main">
      <router-view />
    </main>

    <footer class="app-footer">© 2026 {{ t('app.title') }} Demo</footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './store/auth'
import { useI18n } from 'vue-i18n'

// =========================
// Requirements Traceability
// =========================
// W1: 所有“非商品信息”的多语言文案来自 i18n json（zh/en/ja/zh-TW），并提供语言切换按钮。
// A2: 登录后能力（cart/orders/admin）入口在顶部菜单中，未登录仅显示 login/register。

const router = useRouter()
const auth = useAuthStore()
const keyword = ref('')
const { t, locale } = useI18n()

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
function goAdminReviews() { router.push('/admin/reviews') }
function goAdminReports() { router.push('/admin/reports') }

const currentLangLabel = computed(() => {
  const l = String(locale.value)
  if (l === 'zh') return t('lang.short.zh')
  if (l === 'zh-TW') return t('lang.short.zhTW')
  if (l === 'en') return t('lang.short.en')
  if (l === 'ja') return t('lang.short.ja')
  return l
})

function setLang(l: 'zh' | 'zh-TW' | 'en' | 'ja') {
  locale.value = l
  localStorage.setItem('lang', l)
  document.documentElement.lang = l
}

onMounted(() => {
  auth.tryRestore()
  document.documentElement.lang = String(locale.value)
})
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  padding: 12px 20px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(24, 52, 110, 0.06);
  gap: 8px;
  position: sticky;
  top: 0;
  z-index: 20;
}
.logo { font-weight: 700; text-decoration: none; color: var(--brand-700); font-size: 18px; }
.spacer { flex: 1; min-width: 12px; }
.el-dropdown-link { color: var(--brand-800); font-weight: 600; }
.ml8 { margin-left: 8px; }
.ml16 { margin-left: 16px; }
.app-main { padding: 24px 16px 40px; min-height: calc(100vh - 140px); max-width: 1280px; margin: 0 auto; }
.app-footer { text-align: center; padding: 16px; color: var(--el-text-color-secondary); border-top: 1px solid var(--el-border-color-light); background: #ffffff; }

@media (max-width: 768px) {
  .app-header { padding: 12px 14px; }
  .logo { width: 100%; }
  .spacer { display: none; }
  .app-main { padding: 20px 12px 32px; }
}
</style>
