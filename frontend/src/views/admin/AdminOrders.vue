<template>
  <div>
    <h2>{{ t('admin.ordersTitle') }}</h2>
    <div class="mb16">
      <el-button @click="load">{{ t('order.refresh') }}</el-button>
    </div>
    <el-table :data="list" v-loading="loading" style="width:100%">
      <el-table-column prop="order_id" :label="t('order.orderId')" width="220">
        <template #default="{ row }">
          <router-link :to="`/admin/orders/${row.order_id}`">{{ row.order_id }}</router-link>
        </template>
      </el-table-column>
      <el-table-column prop="customer_name" :label="t('admin.customerName')" width="160" />
      <el-table-column :label="t('order.createdAt')" width="200">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('order.amount')" width="120">
        <template #default="{ row }">￥{{ row.total_amount.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column :label="t('order.status')" width="120">
        <template #default="{ row }">{{ t(`status.${row.status}`) }}</template>
      </el-table-column>
      <el-table-column :label="t('order.shippedAt')" width="200">
        <template #default="{ row }">{{ row.shipped_at ? formatDate(row.shipped_at) : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('admin.operations')" width="160">
        <template #default="{ row }">
          <el-button type="primary" size="small" :disabled="row.status!=='pending'" @click="ship(row.order_id)">{{ t('admin.ship') }}</el-button>
          <el-button class="ml8" type="danger" size="small" :disabled="row.status!=='pending'" @click="cancel(row.order_id)">{{ t('admin.cancelOrder') }}</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api/http'
import { extractErrorMessage } from '../../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

interface Order { order_id:string; total_amount:number; status:string; shipped_at?:string|null; created_at:string; customer_name:string }

const list = ref<Order[]>([])
const loading = ref(false)
const { t } = useI18n()

async function load(){
  loading.value = true
  try{
    const { data } = await api.get('/api/admin/orders')
    list.value = data
  } finally { loading.value = false }
}

async function ship(orderId: string){
  try {
    await api.post(`/api/admin/orders/${orderId}/ship`)
    await load()
    ElMessage.success(t('admin.shipSuccess'))
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('admin.shipFailed')))
  }
}

async function cancel(orderId: string){
  try {
    await api.post(`/api/admin/orders/${orderId}/cancel`)
    await load()
    ElMessage.success(t('admin.cancelSuccess'))
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('admin.cancelFailed')))
  }
}

function formatDate(s:string){ try{ return new Date(s).toLocaleString() } catch { return s } }

onMounted(load)
</script>
<style scoped>
.mb16{ margin-bottom:16px }
.ml8{ margin-left:8px }
</style>
