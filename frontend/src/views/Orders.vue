<template>
  <div>
    <h2>我的订单</h2>
    <div class="mb16">
      <el-select v-model="status" placeholder="筛选状态" clearable style="width:160px">
        <el-option label="全部" value="" />
        <el-option label="待处理" value="pending" />
        <el-option label="已发货" value="shipped" />
        <el-option label="已取消" value="cancelled" />
        <el-option label="已完成" value="completed" />
      </el-select>
      <el-button class="ml8" @click="load">刷新</el-button>
    </div>
    <el-table :data="filtered" v-loading="loading">
      <el-table-column prop="order_id" label="订单号" width="200">
        <template #default="{ row }">
          <router-link :to="`/orders/${row.order_id}`">{{ row.order_id }}</router-link>
        </template>
      </el-table-column>
      <el-table-column label="下单时间" width="200">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="120">
        <template #default="{ row }">￥{{ row.total_amount.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" />
    </el-table>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/http'

interface OrderItem { sku_id:number; quantity:number; unit_price:number; option_values:string }
interface Order { order_id:string; total_amount:number; status:string; shipped_at?:string|null; created_at:string; items:OrderItem[] }

const list = ref<Order[]>([])
const loading = ref(false)
const status = ref<string>('')

async function load(){
  loading.value = true
  try{
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
.mb16{ margin-bottom:16px }
.ml8{ margin-left:8px }
</style>
