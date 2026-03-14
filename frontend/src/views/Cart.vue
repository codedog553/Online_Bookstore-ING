<template>
  <div>
    <h2>{{ t('cart.title') }}</h2>
    <el-table :data="items" v-loading="loading" style="width:100%">
      <el-table-column :label="t('cart.product')" prop="product_title" width="260" />
      <el-table-column :label="t('cart.config')" width="180">
        <template #default="{ row }">
          <span>{{ parseOption(row.option_values) }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('cart.unitPrice')" width="120">
        <template #default="{ row }">￥{{ row.unit_price.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column :label="t('cart.quantity')" width="160">
        <template #default="{ row }">
          <el-input-number v-model="row.quantity" :min="1" @change="(v:number)=>updateQty(row, v)" />
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
      <router-link to="/checkout"><el-button type="primary">{{ t('cart.checkout') }}</el-button></router-link>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/http'
import { extractErrorMessage } from '../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

interface CartItem { id:number; sku_id:number; quantity:number; product_title:string; option_values:string; unit_price:number; subtotal:number }

const items = ref<CartItem[]>([])
const loading = ref(false)
const { t } = useI18n()

function parseOption(s: string){
  try { const obj = JSON.parse(s); if (obj.version) return `${t('product.version')}：${obj.version}`; } catch{}
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

onMounted(load)
</script>
<style scoped>
.total{ display:flex; justify-content:flex-end; gap:12px; margin-top:16px; align-items:center }
</style>
