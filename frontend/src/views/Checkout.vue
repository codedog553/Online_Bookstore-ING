<template>
  <div>
    <h2>结算</h2>
    <el-row :gutter="20">
      <el-col :span="12">
        <h3>收货地址</h3>
        <el-radio-group v-model="selectedAddressId">
          <div v-for="a in addresses" :key="a.id" class="addr-item">
            <el-radio :label="a.id">
              {{ a.receiver_name }} {{ a.phone }}
              <div class="addr-detail">{{ a.province }}{{ a.city }}{{ a.district }} {{ a.detail_address }}</div>
            </el-radio>
          </div>
        </el-radio-group>
        <el-divider />
        <h3>新增地址</h3>
        <el-form :model="addr" label-width="90px" class="addr-form">
          <el-form-item label="收货人"><el-input v-model="addr.receiver_name" /></el-form-item>
          <el-form-item label="电话"><el-input v-model="addr.phone" /></el-form-item>
          <el-form-item label="省"><el-input v-model="addr.province" /></el-form-item>
          <el-form-item label="市"><el-input v-model="addr.city" /></el-form-item>
          <el-form-item label="区县"><el-input v-model="addr.district" /></el-form-item>
          <el-form-item label="详细地址"><el-input v-model="addr.detail_address" /></el-form-item>
          <el-form-item>
            <el-button @click="createAddress">保存并选择</el-button>
          </el-form-item>
        </el-form>
      </el-col>
      <el-col :span="12">
        <h3>订单概览</h3>
        <el-table :data="items" size="small">
          <el-table-column prop="product_title" label="商品" />
          <el-table-column label="配置">
            <template #default="{ row }">{{ parseOption(row.option_values) }}</template>
          </el-table-column>
          <el-table-column label="数量" width="80">
            <template #default="{ row }">{{ row.quantity }}</template>
          </el-table-column>
          <el-table-column label="小计" width="120">
            <template #default="{ row }">￥{{ (row.unit_price * row.quantity).toFixed(2) }}</template>
          </el-table-column>
        </el-table>
        <div class="sum">总计：<b>￥{{ total.toFixed(2) }}</b></div>
        <el-button type="primary" @click="placeOrder" :disabled="!selectedAddressId">下单</el-button>
      </el-col>
    </el-row>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/http'

interface Address{ id:number; receiver_name:string; phone?:string; province:string; city:string; district:string; detail_address:string }
interface CartItem { id:number; sku_id:number; quantity:number; product_title:string; option_values:string; unit_price:number; subtotal:number }

const router = useRouter()
const addresses = ref<Address[]>([])
const selectedAddressId = ref<number | null>(null)
const items = ref<CartItem[]>([])
const addr = ref({ receiver_name:'', phone:'', province:'', city:'', district:'', detail_address:'', is_default:true })

function parseOption(s: string){ try{ const o = JSON.parse(s); return o.version? `版本：${o.version}`: s }catch{ return s } }
const total = computed(()=> items.value.reduce((acc, it)=> acc + it.unit_price * it.quantity, 0))

async function load(){
  const { data: addrData } = await api.get('/api/addresses')
  addresses.value = addrData
  if (addresses.value.length>0) selectedAddressId.value = addresses.value[0].id
  const { data: cart } = await api.get('/api/cart')
  items.value = cart
}

async function createAddress(){
  try {
    const { data } = await api.post('/api/addresses', addr.value)
    addresses.value.unshift(data)
    selectedAddressId.value = data.id
    alert('地址已保存')
  } catch (e:any) {
    alert(e?.response?.data?.detail || '保存失败')
  }
}

async function placeOrder(){
  try {
    const { data } = await api.post('/api/orders', { address_id: selectedAddressId.value })
    alert('下单成功')
    router.push(`/orders/${data.order_id}`)
  } catch (e:any) {
    alert(e?.response?.data?.detail || '下单失败')
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
