<template>
  <div>
    <h2>购物车</h2>
    <el-table :data="items" v-loading="loading" style="width:100%">
      <el-table-column label="商品" prop="product_title" width="260" />
      <el-table-column label="配置" width="180">
        <template #default="{ row }">
          <span>{{ parseOption(row.option_values) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="单价" width="120">
        <template #default="{ row }">￥{{ row.unit_price.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="数量" width="160">
        <template #default="{ row }">
          <el-input-number v-model="row.quantity" :min="1" @change="(v:number)=>updateQty(row, v)" />
        </template>
      </el-table-column>
      <el-table-column label="小计" width="120">
        <template #default="{ row }">￥{{ (row.unit_price * row.quantity).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button type="danger" size="small" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="total">
      <div>总计：<b>￥{{ total.toFixed(2) }}</b></div>
      <router-link to="/checkout"><el-button type="primary">去结算</el-button></router-link>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/http'

interface CartItem { id:number; sku_id:number; quantity:number; product_title:string; option_values:string; unit_price:number; subtotal:number }

const items = ref<CartItem[]>([])
const loading = ref(false)

function parseOption(s: string){
  try { const obj = JSON.parse(s); if (obj.version) return `版本：${obj.version}`; } catch{}
  return s
}

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
    alert(e?.response?.data?.detail || '更新失败')
  }
}

async function remove(row: CartItem){
  try {
    await api.delete(`/api/cart/items/${row.id}`)
    await load()
  } catch (e:any) {
    alert(e?.response?.data?.detail || '删除失败')
  }
}

const total = computed(()=> items.value.reduce((acc, it)=> acc + it.unit_price * it.quantity, 0))

onMounted(load)
</script>
<style scoped>
.total{ display:flex; justify-content:flex-end; gap:12px; margin-top:16px; align-items:center }
</style>
