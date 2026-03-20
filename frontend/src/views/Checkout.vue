<template>
  <div>
    <h2>{{ t('order.checkoutTitle') }}</h2>
    <el-row :gutter="20">
      <el-col :span="12">
        <h3>{{ t('order.address') }}</h3>
        <el-form :model="addr" label-width="90px" class="addr-form">
          <el-form-item :label="t('order.receiverName')"><el-input v-model="addr.receiver_name" /></el-form-item>
          <el-form-item :label="t('order.phone')"><el-input v-model="addr.phone" /></el-form-item>
          <el-form-item :label="t('order.province')"><el-input v-model="addr.province" /></el-form-item>
          <el-form-item :label="t('order.city')"><el-input v-model="addr.city" /></el-form-item>
          <el-form-item :label="t('order.district')"><el-input v-model="addr.district" /></el-form-item>
          <el-form-item :label="t('order.detailAddress')"><el-input v-model="addr.detail_address" /></el-form-item>
          <el-form-item>
            <el-button :loading="savingAddress" @click="saveLastAddress">{{ t('order.saveAddress') }}</el-button>
          </el-form-item>
        </el-form>
      </el-col>
      <el-col :span="12">
        <h3>{{ t('order.orderOverview') }}</h3>
        <el-table :data="items" size="small">
          <el-table-column prop="product_title" :label="t('cart.product')" />
          <el-table-column :label="t('cart.config')">
            <template #default="{ row }">{{ (rowOptionsForParse = row.product_options || null, parseOption(row.option_values)) }}</template>
          </el-table-column>
          <el-table-column :label="t('cart.quantity')" width="80">
            <template #default="{ row }">{{ row.quantity }}</template>
          </el-table-column>
          <el-table-column :label="t('cart.subtotal')" width="120">
            <template #default="{ row }">￥{{ (row.unit_price * row.quantity).toFixed(2) }}</template>
          </el-table-column>
        </el-table>
        <div class="sum">{{ t('cart.total') }}：<b>￥{{ total.toFixed(2) }}</b></div>
        <el-alert
          v-if="hasOutOfStock"
          :title="t('cart.outOfStockInCart')"
          type="error"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />
        <el-button type="primary" :loading="placing" @click="placeOrder" :disabled="!canPlace">{{ t('order.placeOrder') }}</el-button>
      </el-col>
    </el-row>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/http'
import { extractErrorMessage } from '../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { formatOptionValues } from '../utils/productI18n'

// =========================
// Requirements Traceability
// =========================
// A2: 结算页必须登录（路由 requiresAuth）。
// A1: 系统只记忆“上一次填写的地址”；注册时填的地址会成为第一次下单默认地址。
// A11: 结算会创建订单并清空购物车（后端 /api/orders 实现）。
// A8: 展示购物车行项目与总金额。
// D5: 若购物车中有缺货/不可售项，则醒目提示并禁止下单。
// W2: 配置值的展示遵循商品双语规则（formatOptionValues）。

interface CartItem {
  id:number
  sku_id:number
  quantity:number
  product_title:string
  option_values:string
  unit_price:number
  subtotal:number
  product_options?: string | null
  stock_quantity?: number | null
  is_available?: boolean | null
}

const router = useRouter()
const items = ref<CartItem[]>([])
const { t, locale } = useI18n()

const addr = ref({ receiver_name:'', phone:'', province:'', city:'', district:'', detail_address:'', is_default:true })
const savingAddress = ref(false)
const placing = ref(false)

function parseOption(s: string){
  // Checkout cart items come from /api/cart and include product_options
  return formatOptionValues(s, rowOptionsForParse.value, String(locale.value), (k) => {
    const key = (k || '').toLowerCase()
    if (key.includes('version') || k === '版本') return t('product.version')
    return k
  })
}

const rowOptionsForParse = ref<string | null>(null)
const total = computed(()=> items.value.reduce((acc, it)=> acc + it.unit_price * it.quantity, 0))

const hasOutOfStock = computed(() => {
  return items.value.some((it) => it.is_available === false || (it.stock_quantity != null && it.quantity > it.stock_quantity))
})

const canPlace = computed(() => {
  if (!items.value.length) return false
  if (hasOutOfStock.value) return false
  return Boolean(addr.value.receiver_name && addr.value.province && addr.value.city && addr.value.district && addr.value.detail_address)
})

async function load(){
  // A1: 预填“上一次地址”（last address）。
  try {
    const { data } = await api.get('/api/addresses/last')
    addr.value.receiver_name = data.receiver_name || ''
    addr.value.phone = data.phone || ''
    addr.value.province = data.province || ''
    addr.value.city = data.city || ''
    addr.value.district = data.district || ''
    addr.value.detail_address = data.detail_address || ''
  } catch {
    // 404 没有地址记录，保持空表单即可
  }
  const { data: cart } = await api.get('/api/cart')
  items.value = cart
}

async function saveLastAddress(){
  // A1/A11: 更新 last address，供下一次结算自动预填。
  savingAddress.value = true
  try {
    await api.put('/api/addresses/last', addr.value)
    ElMessage.success(t('msg.saveAddressSuccess'))
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.saveFailed')))
  } finally {
    savingAddress.value = false
  }
}

async function placeOrder(){
  // A11: 下单成功后，后端会清空购物车。
  if (!canPlace.value) return
  placing.value = true
  try {
    const { data } = await api.post('/api/orders', { address: {
      receiver_name: addr.value.receiver_name,
      phone: addr.value.phone || undefined,
      province: addr.value.province,
      city: addr.value.city,
      district: addr.value.district,
      detail_address: addr.value.detail_address,
    } })
    ElMessage.success(t('order.placeOrderSuccess'))
    router.push(`/orders/${data.order_id}`)
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('order.placeOrderFailed')))
  } finally {
    placing.value = false
  }
}

onMounted(load)
</script>
<style scoped>
.addr-item{ margin:8px 0 }
.addr-detail{ color:#666; font-size:12px }
.addr-form{ max-width: 480px }
.sum{ text-align:right; margin:12px 0 }
</style>
