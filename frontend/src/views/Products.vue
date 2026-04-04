<template>
  <div class="products-page">
    <el-row :gutter="16">
      <el-col :span="24" class="mb16">
        <div class="products-toolbar">
          <el-input
            v-model="keyword"
            :placeholder="t('app.searchPlaceholder')"
            style="max-width: 320px"
            @keyup.enter="load"
          />
          <el-button class="ml8" type="primary" @click="load">{{ t('app.search') }}</el-button>
        </div>
      </el-col>
      <el-col v-for="p in products" :key="p.id" :span="6" :xs="24" :sm="12" :md="8" :lg="6" class="mb16">
        <el-card shadow="hover" class="product-card" @click="goDetail(p.id)">
          <img
            class="product-thumb"
            :src="productThumb(p)"
            :alt="pickText(p.title, p.title_en)"
          />
          <div class="product-info">
            <div class="mt8 title">{{ pickText(p.title, p.title_en) }}</div>
            <div class="price">￥{{ p.min_price ?? p.base_price }}</div>
          </div>
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
.products-toolbar{ display:flex; align-items:center; gap:8px; padding:12px 14px; background:#ffffff; border:1px solid var(--el-border-color-light); border-radius:12px; box-shadow: 0 6px 16px rgba(24,52,110,0.06); }
.product-card{ cursor:pointer; transition: transform 0.15s ease, box-shadow 0.15s ease; }
.product-card:hover{ transform: translateY(-2px); box-shadow: 0 10px 22px rgba(24,52,110,0.12); }
.product-thumb{ width:100%; height:170px; object-fit:cover; border-radius:10px; border:1px solid var(--el-border-color-light); background:#f7faff; }
.product-info{ padding: 8px 2px 2px; }
.title{ font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color: var(--brand-800); }
.price{ color: var(--brand-600); margin-top:4px; font-weight:600 }
.mb16{ margin-bottom:16px }
.mt8{ margin-top:8px }
.ml8{ margin-left:8px }
.center{ display:flex; justify-content:center; margin-top:16px }
</style>
