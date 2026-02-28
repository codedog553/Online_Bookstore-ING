<template>
  <div v-if="product">
    <el-row :gutter="20">
      <el-col :span="10">
        <ImageCarousel :images="product.images" />
      </el-col>
      <el-col :span="14">
        <h2>{{ product.title }}</h2>
        <p style="color:#666" v-if="product.author">作者：{{ product.author }}</p>
        <div class="price">￥{{ displayPrice }}</div>

        <div v-if="versions.length" class="mt16">
          <span>版本：</span>
          <el-select v-model="selectedVersion" placeholder="请选择版本" style="width:160px">
            <el-option v-for="v in versions" :key="v" :label="v" :value="v" />
          </el-select>
        </div>

        <div class="mt16">
          <span>数量：</span>
          <el-input-number v-model="qty" :min="1" />
        </div>

        <div class="mt16">
          <el-button type="primary" @click="addToCart">加入购物车</el-button>
        </div>
      </el-col>
    </el-row>

    <div class="mt24">
      <h3>评论</h3>
      <el-form :model="review" label-width="80px" class="mb16">
        <el-form-item label="评分">
          <el-rate v-model="review.rating" :max="5" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input type="textarea" v-model="review.comment" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitReview">提交</el-button>
        </el-form-item>
      </el-form>
      <el-empty v-if="reviews.length===0" description="暂无评论" />
      <el-timeline v-else>
        <el-timeline-item v-for="r in reviews" :key="r.id" :timestamp="formatDate(r.created_at)">
          <div>评分：{{ r.rating }}/5</div>
          <div style="white-space:pre-wrap">{{ r.comment || '（无文字）' }}</div>
        </el-timeline-item>
      </el-timeline>
    </div>
  </div>
  <el-empty v-else description="加载中..." />
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/http'
import ImageCarousel from '../components/ImageCarousel.vue'

interface SKU { id:number; option_values:string; price_adjustment:number; stock_quantity:number; is_available:boolean }
interface Product { id:number; title:string; author?:string; base_price:number; min_price?:number|null; max_price?:number|null; images?:string|null; options?:string|null; skus:SKU[] }
interface Review { id:number; rating:number; comment?:string|null; created_at:string }

const route = useRoute()
const product = ref<Product | null>(null)
const selectedVersion = ref<string>('')
const qty = ref(1)
const reviews = ref<Review[]>([])
const review = ref({ rating: 5, comment: '' })

const versions = computed(() => {
  try {
    if (product.value?.options) {
      const obj = JSON.parse(product.value.options)
      const list = obj?.version
      if (Array.isArray(list)) return list as string[]
    }
  } catch {}
  return [] as string[]
})

const selectedSku = computed(() => {
  if (!product.value) return null
  const v = selectedVersion.value
  for (const s of product.value.skus) {
    try {
      const ov = JSON.parse(s.option_values)
      if (ov?.version === v) return s
    } catch {}
  }
  return null
})

const displayPrice = computed(() => {
  const base = product.value ? Number(product.value.base_price) : 0
  const adj = selectedSku.value ? Number(selectedSku.value.price_adjustment || 0) : 0
  return (base + adj).toFixed(2)
})

async function load() {
  const id = Number(route.params.id)
  const { data } = await api.get(`/api/products/${id}`)
  product.value = data
  // 默认选择第一个版本
  if (versions.value.length && !selectedVersion.value) selectedVersion.value = versions.value[0]
  const rv = await api.get(`/api/products/${id}/reviews`)
  reviews.value = rv.data
}

async function addToCart() {
  if (!selectedSku.value) {
    alert('请选择版本')
    return
  }
  try {
    await api.post('/api/cart/items', { sku_id: selectedSku.value.id, quantity: qty.value })
    alert('已加入购物车')
  } catch (e:any) {
    alert(e?.response?.data?.detail || '添加失败（可能需要登录）')
  }
}

async function submitReview() {
  const id = Number(route.params.id)
  try {
    await api.post(`/api/products/${id}/reviews`, review.value)
    const rv = await api.get(`/api/products/${id}/reviews`)
    reviews.value = rv.data
    review.value = { rating:5, comment:'' }
  } catch (e:any) {
    alert(e?.response?.data?.detail || '评论失败（需购买后评论）')
  }
}

function formatDate(s:string){
  try { return new Date(s).toLocaleString() } catch { return s }
}

onMounted(load)
</script>
<style scoped>
.price{ color:#f40; font-size:20px; margin-top:8px }
.mt16{ margin-top:16px }
.mt24{ margin-top:24px }
.mb16{ margin-bottom:16px }
</style>
