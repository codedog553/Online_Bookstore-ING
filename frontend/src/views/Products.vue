<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="24" class="mb16">
        <el-input v-model="keyword" placeholder="输入书名关键字" style="max-width: 320px" @keyup.enter="load" />
        <el-button class="ml8" type="primary" @click="load">搜索</el-button>
      </el-col>
      <el-col v-for="p in products" :key="p.id" :span="6" class="mb16">
        <el-card shadow="hover" @click="goDetail(p.id)" style="cursor:pointer">
          <img :src="firstImage(p.images)" alt="封面" style="width:100%;height:160px;object-fit:cover" />
          <div class="mt8 title">{{ p.title }}</div>
          <div class="price">￥{{ p.min_price ?? p.base_price }}</div>
        </el-card>
      </el-col>
    </el-row>
    <div class="center">
      <el-pagination
        layout="prev, pager, next"
        :page-size="size"
        :current-page="page"
        @current-change="(p:number)=>{page=p;load()}"
        :total="totalApprox"
      />
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/http'

interface Product {
  id:number; title:string; base_price:number; min_price?:number|null; images?:string|null
}

const route = useRoute();
const router = useRouter();
const products = ref<Product[]>([])
const page = ref(1)
const size = ref(20)
const totalApprox = ref(200) // 简化：后端未返回总数，用一个大概值
const keyword = ref<string>((route.query.keyword as string) || '')

function firstImage(images?: string | null) {
  try { if (images){ const arr = JSON.parse(images); if (Array.isArray(arr) && arr.length>0) return arr[0]; } } catch {}
  return 'https://via.placeholder.com/400x240?text=No+Image'
}

async function load(){
  const params:any = { page: page.value, size: size.value }
  if (keyword.value) params.keyword = keyword.value
  const { data } = await api.get('/api/products', { params })
  products.value = data
  // 同步路由查询
  router.replace({ path: '/products', query: { keyword: keyword.value || undefined } })
}

onMounted(load)
watch(() => route.query.keyword, (v)=>{ keyword.value = (v as string)||''; page.value=1; load(); })

function goDetail(id:number){ router.push(`/products/${id}`) }
</script>
<style scoped>
.title{ font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.price{ color:#f40; margin-top:4px }
.mb16{ margin-bottom:16px }
.mt8{ margin-top:8px }
.ml8{ margin-left:8px }
.center{ display:flex; justify-content:center; margin-top:16px }
</style>
