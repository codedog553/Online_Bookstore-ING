<template>
  <div>
    <h2>{{ t('order.detail') }}</h2>
    <el-descriptions v-if="order" :column="2" border>
      <el-descriptions-item :label="t('order.orderId')">{{ order.order_id }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.status')">{{ order.status }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.createdAt')">{{ formatDate(order.created_at) }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.shippedAt')">{{ order.shipped_at ? formatDate(order.shipped_at) : '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('order.amount')" :span="2">￥{{ order.total_amount.toFixed(2) }}</el-descriptions-item>
    </el-descriptions>

    <h3 class="mt16">{{ t('cart.product') }}</h3>
    <el-table :data="order?.items || []" size="small">
      <el-table-column :label="t('cart.config')">
        <template #default="{ row }">{{ parseOption(row.option_values) }}</template>
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
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/http'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

interface OrderItem { sku_id:number; quantity:number; unit_price:number; option_values:string }
interface Order { order_id:string; total_amount:number; status:string; shipped_at?:string|null; created_at:string; items:OrderItem[] }

const route = useRoute()
const router = useRouter()
const order = ref<Order | null>(null)
const { t } = useI18n()

function parseOption(s: string){
  try{
    const o = JSON.parse(s)
    return o.version? `${t('product.version')}：${o.version}`: s
  }catch{ return s }
}
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
    ElMessage.error(e?.response?.data?.detail || t('order.cancelFailed'))
  }
}

onMounted(load)
</script>
<style scoped>
.mt16{ margin-top:16px }
</style>
