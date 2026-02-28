<template>
  <div>
    <h2>后台 - 订单管理</h2>
    <div class="mb16">
      <el-button @click="load">刷新</el-button>
    </div>
    <el-table :data="list" v-loading="loading" style="width:100%">
      <el-table-column prop="order_id" label="订单号" width="220" />
      <el-table-column label="下单时间" width="200">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="120">
        <template #default="{ row }">￥{{ row.total_amount.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column label="发货时间" width="200">
        <template #default="{ row }">{{ row.shipped_at ? formatDate(row.shipped_at) : '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button type="primary" size="small" :disabled="row.status!=='pending'" @click="ship(row.order_id)">标记发货</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api/http'

interface Order { order_id:string; total_amount:number; status:string; shipped_at?:string|null; created_at:string }

const list = ref<Order[]>([])
const loading = ref(false)

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
  } catch (e:any) {
    alert(e?.response?.data?.detail || '操作失败（需要管理员登录）')
  }
}

function formatDate(s:string){ try{ return new Date(s).toLocaleString() } catch { return s } }

onMounted(load)
</script>
<style scoped>
.mb16{ margin-bottom:16px }
</style>
