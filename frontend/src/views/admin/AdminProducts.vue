<template>
  <div>
    <h2>后台 - 商品管理</h2>

    <el-card class="mb16">
      <template #header>新增商品</template>
      <el-form :model="form" label-width="90px" @keyup.enter.native="create">
        <el-form-item label="书名"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="作者"><el-input v-model="form.author" /></el-form-item>
        <el-form-item label="基础价格"><el-input v-model.number="form.base_price" type="number" /></el-form-item>
        <el-form-item label="上架"><el-switch v-model="form.is_active" /></el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="create">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="list" v-loading="loading" style="width:100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="书名" />
      <el-table-column prop="author" label="作者" width="160" />
      <el-table-column label="价格" width="140">
        <template #default="{ row }">￥{{ (row.min_price ?? row.base_price).toFixed ? (row.min_price ?? row.base_price).toFixed(2) : row.min_price ?? row.base_price }}</template>
      </el-table-column>
      <el-table-column label="上架" width="120">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" @change="() => toggleActive(row)" />
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api/http'

interface Product { id:number; title:string; author?:string; base_price:number; min_price?:number|null; is_active:boolean }

const list = ref<Product[]>([])
const loading = ref(false)
const saving = ref(false)
const form = ref({ title:'', author:'', base_price: 0, is_active: true })

async function load(){
  loading.value = true
  try {
    const { data } = await api.get('/api/admin/products')
    list.value = data
  } finally { loading.value = false }
}

async function create(){
  if (!form.value.title || !form.value.base_price) return alert('请填写书名和价格')
  saving.value = true
  try {
    await api.post('/api/admin/products', form.value)
    form.value = { title:'', author:'', base_price: 0, is_active: true }
    await load()
  } catch(e:any){
    alert(e?.response?.data?.detail || '保存失败（需要管理员登录）')
  } finally { saving.value = false }
}

async function toggleActive(row: Product){
  try {
    await api.put(`/api/admin/products/${row.id}`, { is_active: row.is_active })
  } catch (e:any) {
    alert(e?.response?.data?.detail || '更新失败')
  }
}

onMounted(load)
</script>
<style scoped>
.mb16{ margin-bottom:16px }
</style>
