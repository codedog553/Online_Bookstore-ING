<template>
  <div>
    <h2>{{ t('order.detail') }}</h2>
    <el-descriptions v-if="order" :column="2" border>
      <el-descriptions-item :label="t('order.orderId')">{{ order.order_id }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.status')">{{ t(`status.${order.status}`) }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.createdAt')">{{ formatDate(order.created_at) }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.shippedAt')">{{ order.shipped_at ? formatDate(order.shipped_at) : '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.cancelledAt')">{{ order.cancelled_at ? formatDate(order.cancelled_at) : '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.completedAt')">{{ order.completed_at ? formatDate(order.completed_at) : '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.amount')" :span="2">￥{{ order.total_amount.toFixed(2) }}</el-descriptions-item>
    </el-descriptions>

    <div v-if="order?.shipping_address" class="mt16">
      <h3>{{ t('order.address') }}</h3>
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="t('order.receiverName')">{{ order.shipping_address.receiver_name }}</el-descriptions-item>
        <el-descriptions-item :label="t('order.phone')">{{ order.shipping_address.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('order.province')">{{ order.shipping_address.province }}</el-descriptions-item>
        <el-descriptions-item :label="t('order.city')">{{ order.shipping_address.city }}</el-descriptions-item>
        <el-descriptions-item :label="t('order.district')">{{ order.shipping_address.district }}</el-descriptions-item>
        <el-descriptions-item :label="t('order.detailAddress')" :span="2">{{ order.shipping_address.detail_address }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-if="(order?.status_timeline || []).length" class="mt16">
      <h3>{{ t('order.statusTimeline') }}</h3>
      <el-timeline>
        <el-timeline-item
          v-for="ev in order?.status_timeline || []"
          :key="ev.id"
          :timestamp="formatDate(ev.created_at)"
        >
          {{ t(`status.${ev.status}`) }}
        </el-timeline-item>
      </el-timeline>
    </div>

    <h3 class="mt16">{{ t('cart.product') }}</h3>
    <el-table :data="order?.items || []" size="small">
      <el-table-column :label="t('cart.product')" width="260">
        <template #default="{ row }">
          <router-link :to="`/products/${row.product_id}`">{{ displayProductTitle(row) }}</router-link>
        </template>
      </el-table-column>
      <el-table-column :label="t('cart.config')">
        <template #default="{ row }">{{ (rowOptionsForParse = row.product_options || null, parseOption(row.option_values)) }}</template>
      </el-table-column>
      <el-table-column :label="t('cart.quantity')" width="80">
        <template #default="{ row }">{{ row.quantity }}</template>
      </el-table-column>
      <el-table-column :label="t('cart.unitPrice')" width="120">
        <template #default="{ row }">￥{{ row.unit_price.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column :label="t('cart.subtotal')" width="120">
        <template #default="{ row }">￥{{ (row.unit_price * row.quantity).toFixed(2) }}</template>
      </el-table-column>
    </el-table>

    <div class="mt16">
      <el-button type="danger" v-if="order?.status==='pending'" @click="cancel">{{ t('order.cancel') }}</el-button>
      <el-button type="success" class="ml8" v-if="order?.status==='shipped'" @click="complete">{{ t('order.confirmReceived') }}</el-button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/http'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { extractErrorMessage } from '../api/error'
import { formatOptionValues, pickProductText } from '../utils/productI18n'

interface OrderStatusEvent { id:number; status:string; note?:string|null; created_at:string }
interface ShippingAddress { receiver_name:string; phone?:string|null; province:string; city:string; district:string; detail_address:string }
interface OrderItem {
  sku_id:number
  quantity:number
  unit_price:number
  option_values:string
  product_id:number
  product_title:string
  product_title_en?: string | null
  product_options?: string | null
}
interface Order {
  order_id:string
  total_amount:number
  status:string
  shipped_at?:string|null
  completed_at?:string|null
  cancelled_at?:string|null
  created_at:string
  items:OrderItem[]
  shipping_address?: ShippingAddress | null
  status_timeline?: OrderStatusEvent[]
}

const route = useRoute()
const router = useRouter()
const order = ref<Order | null>(null)
const { t, locale } = useI18n()

function displayProductTitle(row: OrderItem) {
  return pickProductText(row.product_title, row.product_title_en || undefined, String(locale.value))
}

function parseOption(s: string){
  return formatOptionValues(s, rowOptionsForParse.value, String(locale.value), (k) => {
    const key = (k || '').toLowerCase()
    if (key.includes('version') || k === '版本') return t('product.version')
    return k
  })
}

// see Cart.vue: keep parseOption signature, provide per-row options via assignment in template.
const rowOptionsForParse = ref<string | null>(null)
function formatDate(s:string){ try{ return new Date(s).toLocaleString() } catch { return s } }

async function load(){
  const id = route.params.orderId as string
  const { data } = await api.get(`/api/orders/${id}`)
  order.value = data
}

async function cancel(){
  if (!order.value) return
  try{
    await api.post(`/api/orders/${order.value.order_id}/cancel`)
    await load()
    ElMessage.success(t('order.cancelSuccess'))
  }catch(e:any){
    ElMessage.error(extractErrorMessage(e, t('order.cancelFailed')))
  }
}

async function complete(){
  if (!order.value) return
  try {
    await api.post(`/api/orders/${order.value.order_id}/complete`)
    await load()
    ElMessage.success(t('order.confirmReceivedSuccess'))
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('order.confirmReceivedFailed')))
  }
}

onMounted(load)
</script>
<style scoped>
.mt16{ margin-top:16px }
.ml8{ margin-left:8px }
</style>
