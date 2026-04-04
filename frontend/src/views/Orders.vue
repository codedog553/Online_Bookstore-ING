<template>
  <div>
    <h2>{{ t('order.myOrdersTitle') }}</h2>
    <div class="filter-bar mb16">
      <el-select v-model="status" :placeholder="t('order.filterStatus')" clearable style="width:160px">
        <el-option :label="t('admin.all')" value="" />
        <el-option :label="t('status.pending')" value="pending" />
        <el-option :label="t('status.shipped')" value="shipped" />
        <el-option :label="t('status.cancelled')" value="cancelled" />
        <el-option :label="t('status.completed')" value="completed" />
      </el-select>
      <el-button class="ml8" @click="load">{{ t('order.refresh') }}</el-button>
    </div>
    <el-table :data="filtered" v-loading="loading">
      <el-table-column prop="order_id" :label="t('order.orderId')" width="200">
        <template #default="{ row }">
          <router-link :to="`/orders/${row.order_id}`">{{ row.order_id }}</router-link>
        </template>
      </el-table-column>
      <el-table-column :label="t('order.createdAt')" width="200">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('order.amount')" width="120">
        <template #default="{ row }">￥{{ row.total_amount.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column :label="t('order.status')" width="120">
        <template #default="{ row }">{{ t(`status.${row.status}`) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/http'
import { useI18n } from 'vue-i18n'

// =========================
// Requirements Traceability
// =========================
// A2: 订单页面必须登录（路由 requiresAuth）。
// A12: 展示用户订单列表（后端已按时间倒序返回）。
// B3: 支持按订单当前状态过滤（pending/shipped/cancelled/completed）。

interface OrderItem { sku_id:number; quantity:number; unit_price:number; option_values:string }
interface Order { order_id:string; total_amount:number; status:string; shipped_at?:string|null; created_at:string; items:OrderItem[] }

const list = ref<Order[]>([])
const loading = ref(false)
const status = ref<string>('')
const { t } = useI18n()

async function load(){
  loading.value = true
  try{
    // A12/B3: 后端接口支持 status 参数过滤；本页当前实现用前端过滤（filtered computed）。
    //         若要改为后端过滤，可传 /api/orders?status=pending（本任务按系统规则不改逻辑，仅注释说明）。
    const { data } = await api.get('/api/orders')
    list.value = data
  } finally {
    loading.value = false
  }
}

const filtered = computed(()=> status.value ? list.value.filter(x=> x.status===status.value) : list.value)
function formatDate(s:string){ try{ return new Date(s).toLocaleString() } catch { return s } }

onMounted(load)
</script>
<style scoped>
.filter-bar{ display:flex; align-items:center; gap:8px; padding:12px 14px; background:#ffffff; border:1px solid var(--el-border-color-light); border-radius:12px; box-shadow: 0 6px 16px rgba(24,52,110,0.06); }
.mb16{ margin-bottom:16px }
.ml8{ margin-left:8px }
</style>
