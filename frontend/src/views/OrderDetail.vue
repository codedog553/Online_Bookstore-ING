<template>
  <div>
    <h2>订单详情</h2>
    <el-descriptions v-if="order" :column="2" border>
      <el-descriptions-item label="订单号">{{ order.order_id }}</el-descriptions-item>
      <el-descriptions-item label="状态">{{ order.status }}</el-descriptions-item>
      <el-descriptions-item label="下单时间">{{ formatDate(order.created_at) }}</el-descriptions-item>
      <el-descriptions-item label="发货时间">{{ order.shipped_at ? formatDate(order.shipped_at) : '-' }}</el-descriptions-item>
      <el-descriptions-item label="金额" :span="2">￥{{ order.total_amount.toFixed(2) }}</el-descriptions-item>
    </el-descriptions>

    <h3 class="mt16">商品列表</h3>
    <el-table :data="order?.items || []" size="small">
      <el-table-column label="配置">
        <template #default="{ row }">{{ parseOption(row.option_values) }}</template>
      </el-table-column>
      <el-table-column label="数量" width="80">
        <template #default="{ row }">{{ row.quantity }}</template>
      </el-table-column>
      <el-table-column label="单价" width="120">
        <template #default="{ row }">￥{{ row.unit_price.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="小计" width="120">
        <template #default="{ row }">￥{{ (row.unit_price * row.quantity).toFixed(2) }}</template>
      </el-table-column>
    </el-table>

    <div class="mt16">
      <el-button type="danger" v-if="order?.status==='pending'" @click="cancel">取消订单</el-button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/http'

interface OrderItem { sku_id:number; quantity:number; unit_price:number; option_values:string }
interface Order { order_id:string; total_amount:number; status:string; shipped_at?:string|null; created_at:string; items:OrderItem[] }

const route = useRoute()
const router = useRouter()
const order = ref<Order | null>(null)

function parseOption(s: string){ try{ const o = JSON.parse(s); return o.version? `版本：${o.version}`: s }catch{ return s } }
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
    alert('订单已取消')
  }catch(e:any){
    alert(e?.response?.data?.detail || '取消失败')
  }
}

onMounted(load)
</script>
<style scoped>
.mt16{ margin-top:16px }
</style>
