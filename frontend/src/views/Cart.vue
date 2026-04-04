<template>
  <div>
    <h2>{{ t('cart.title') }}</h2>
    <el-table :data="items" v-loading="loading" style="width:100%">
      <el-table-column :label="t('cart.product')" width="260">
        <template #default="{ row }">
          <router-link :to="`/products/${row.product_id}`">{{ displayProductTitle(row) }}</router-link>
        </template>
      </el-table-column>
      <el-table-column :label="t('cart.config')" width="180">
        <template #default="{ row }">
          <span>{{ (rowOptionsForParse = row.product_options || null, parseOption(row.option_values)) }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('cart.unitPrice')" width="120">
        <template #default="{ row }">￥{{ row.unit_price.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column :label="t('cart.quantity')" width="160">
        <template #default="{ row }">
          <div style="display:flex; flex-direction:column; gap:6px">
            <el-input-number
              v-model="row.quantity"
              :min="1"
              :max="row.stock_quantity != null && row.stock_quantity > 0 ? row.stock_quantity : undefined"
              :disabled="row.is_available === false"
              @change="(v:number)=>updateQty(row, v)"
            />
            <el-text v-if="!isRowPurchasable(row)" type="danger" size="small">{{ outOfStockText(row) }}</el-text>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('cart.subtotal')" width="120">
        <template #default="{ row }">￥{{ (row.unit_price * row.quantity).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column :label="t('admin.operations')" width="120">
        <template #default="{ row }">
          <el-button type="danger" size="small" @click="remove(row)">{{ t('cart.remove') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="total">
      <div>{{ t('cart.total') }}：<b>￥{{ total.toFixed(2) }}</b></div>
      <router-link to="/checkout">
        <el-button type="primary" :disabled="!canCheckout">{{ t('cart.checkout') }}</el-button>
      </router-link>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/http'
import { extractErrorMessage } from '../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { formatOptionValues, pickProductText } from '../utils/productI18n'

// =========================
// Requirements Traceability
// =========================
// A2: 购物车页必须登录后访问（路由 requiresAuth）。购物车数据存服务端，跨会话持久化。
// A8: 购物车列表展示商品名/单价/数量/小计，并展示总金额。
// A9: 支持修改购买数量。
// A10: 支持移除购物车项。
// A8: 点击商品名可跳回商品详情页。
// D3: 购物车项以 SKU 为单位，因此同一本书不同版本可同时存在。
// D5: 缺货/不可售项在购物车中做醒目提示，并禁用结算。
// W2: 商品标题/配置值按语言规则显示（pickProductText/formatOptionValues）。

interface CartItem {
  id:number
  sku_id:number
  quantity:number
  product_id:number
  product_title:string
  product_title_en?: string | null
  option_values:string
  unit_price:number
  subtotal:number

  // D5: 后端返回的库存/可售状态，用于购物车提示与禁用结算。
  stock_quantity?: number | null
  is_available?: boolean | null
}

const items = ref<CartItem[]>([])
const loading = ref(false)
const { t, locale } = useI18n()

function displayProductTitle(row: CartItem) {
  return pickProductText(row.product_title, row.product_title_en || undefined, String(locale.value))
}

function parseOption(s: string){
  // W2: translate option values in non-zh locales
  return formatOptionValues(s, rowOptionsForParse.value, String(locale.value), (k) => {
    const key = (k || '').toLowerCase()
    if (key.includes('version') || k === '版本') return t('product.version')
    return k
  })
}

// Helper: formatOptionValues needs product_options per row.
// For backward compatibility, we keep parseOption signature and set a reactive ref when rendering.
import { computed as _computed } from 'vue'
const rowOptionsForParse = ref<string | null>(null)

async function load(){
  loading.value = true
  try {
    const { data } = await api.get('/api/cart')
    items.value = data
  } finally {
    loading.value = false
  }
}

async function updateQty(row: CartItem, v:number){
  try {
    await api.put(`/api/cart/items/${row.id}`, { quantity: row.quantity })
    await load()
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('cart.updateFailed')))
  }
}

async function remove(row: CartItem){
  try {
    await api.delete(`/api/cart/items/${row.id}`)
    await load()
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('cart.removeFailed')))
  }
}

const total = computed(()=> items.value.reduce((acc, it)=> acc + it.unit_price * it.quantity, 0))

function isRowPurchasable(row: CartItem): boolean {
  if (row.is_available === false) return false
  if (row.stock_quantity != null && row.quantity > row.stock_quantity) return false
  return true
}

function outOfStockText(row: CartItem): string {
  if (row.is_available === false) return t('cart.unavailable')
  return t('cart.outOfStockInCart')
}

const canCheckout = computed(() => {
  // D5: 购物车中存在缺货/不可售，则禁止进入结算。
  if (!items.value.length) return false
  return items.value.every(isRowPurchasable)
})

onMounted(load)
</script>
<style scoped>
.total{ display:flex; justify-content:flex-end; gap:12px; margin-top:16px; align-items:center; padding:12px 16px; background:#ffffff; border:1px solid var(--el-border-color-light); border-radius:12px; box-shadow: 0 6px 16px rgba(24,52,110,0.06); }
</style>
