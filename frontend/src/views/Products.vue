<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="24" class="mb16">
        <el-input
          v-model="keyword"
          :placeholder="t('app.searchPlaceholder')"
          style="max-width: 320px"
          @keyup.enter="load"
        />
        <el-button class="ml8" type="primary" @click="load">{{ t('app.search') }}</el-button>
      </el-col>
      <el-col v-for="p in products" :key="p.id" :span="6" class="mb16">
        <el-card shadow="hover" @click="goDetail(p.id)" style="cursor:pointer">
          <img
            :src="productThumb(p)"
            :alt="pickText(p.title, p.title_en)"
            style="width:100%;height:160px;object-fit:cover"
          />
          <div class="mt8 title">{{ pickText(p.title, p.title_en) }}</div>
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
        :total="total"
      />
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/http'
import { useI18n } from 'vue-i18n'
import { pickProductText } from '../utils/productI18n'
import { resolveBackendUrl } from '../utils/resolveUrl'

// =========================
// Requirements Traceability
// =========================
// A2: 本页商品列表允许未登录访问（路由不要求 requiresAuth）。
// A3: 商品列表展示：书名/价格/缩略图。
// A4: 支持按书名关键字搜索（keyword）。
// A5: 使用分页组件导航长列表（后端 page/size/total）。
// W2: 商品信息双语字段（title/title_en）按语言规则显示（pickProductText）。

interface Product {
  id:number
  title:string
  title_en?: string | null
  author?: string | null
  author_en?: string | null
  base_price:number
  min_price?:number|null
  thumbnail_url?: string | null
}

const route = useRoute();
const router = useRouter();
const products = ref<Product[]>([])
const page = ref(1)
const size = ref(20)
const total = ref(0)
const keyword = ref<string>((route.query.keyword as string) || '')

const { locale, t } = useI18n()

function pickText(zh?: string | null, en?: string | null) {
  return pickProductText(zh, en, String(locale.value))
}

function productThumb(p: Product) {
  // A3/B1: prefer backend computed thumbnail_url (supports SKU photos fallback)
  if (p.thumbnail_url) return resolveBackendUrl(p.thumbnail_url)
  return 'https://via.placeholder.com/400x240?text=No+Image'
}

async function load(){
  // A5: 通过分页参数请求后端，返回 items + total。
  const params:any = { page: page.value, size: size.value }
  if (keyword.value) params.keyword = keyword.value
  const { data } = await api.get('/api/products', { params })
  products.value = data.items
  total.value = data.total
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
