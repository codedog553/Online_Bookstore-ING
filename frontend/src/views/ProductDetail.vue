<template>
  <div v-if="product">
    <el-row :gutter="20">
      <el-col :span="10">
        <div v-if="selectedImageUrl" class="main-image">
          <img :src="selectedImageUrl" :alt="pickText(product.title, product.title_en)" />
        </div>
        <ImageCarousel :images="product.images" :alt="pickText(product.title, product.title_en)" />
      </el-col>
      <el-col :span="14">
        <h2>{{ pickText(product.title, product.title_en) }}</h2>
        <p style="color:#666" v-if="pickText(product.author, product.author_en)">
          {{ t('product.author') }}：{{ pickText(product.author, product.author_en) }}
        </p>
        <div class="price">￥{{ displayPrice }}</div>

        <div class="mt16" v-if="reviewCount > 0">
          <el-rate :model-value="avgRating" disabled show-score />
          <span style="margin-left:8px;color:#666">({{ reviewCount }})</span>
        </div>

        <div v-for="name in optionNames" :key="name" class="mt16">
          <span>{{ name }}：</span>
          <el-select v-model="selections[name]" :placeholder="t('product.select')" style="width:180px">
            <el-option v-for="v in optionsMap[name]" :key="v" :label="displayOptionValue(name, v)" :value="v" />
          </el-select>
        </div>

        <div class="mt16">
          <span>{{ t('product.quantity') }}：</span>
          <el-input-number v-model="qty" :min="1" />
          <span v-if="matchedSku && matchedSku.stock_quantity !== null" style="margin-left:8px;color:#666">
            {{ t('product.stock') }}：{{ matchedSku.stock_quantity }}
          </span>
        </div>

        <div class="mt16">
          <el-button type="primary" @click="addToCart" :disabled="!canAddToCart">{{ t('product.addToCart') }}</el-button>
        </div>
      </el-col>
    </el-row>

    <div class="mt24">
      <h3>{{ t('product.reviews') }}</h3>
      <el-form :model="review" label-width="80px" class="mb16">
        <el-form-item :label="t('product.rating')">
          <el-rate v-model="review.rating" :max="5" />
        </el-form-item>
        <el-form-item :label="t('product.comment')">
          <el-input type="textarea" v-model="review.comment" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitReview">{{ t('product.submit') }}</el-button>
        </el-form-item>
      </el-form>
      <el-empty v-if="reviews.length===0" :description="t('product.noReviews')" />
      <el-timeline v-else>
        <el-timeline-item v-for="r in reviews" :key="r.id" :timestamp="formatDate(r.created_at)">
          <div>{{ t('product.rating') }}：{{ r.rating }}/5</div>
          <div style="white-space:pre-wrap">{{ r.comment || t('msg.noText') }}</div>
        </el-timeline-item>
      </el-timeline>
    </div>
  </div>
  <el-empty v-else :description="t('msg.loading')" />
</template>
<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/http'
import ImageCarousel from '../components/ImageCarousel.vue'
import { extractErrorMessage } from '../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

interface SKU { id:number; option_values:string; price_adjustment:number; stock_quantity:number; is_available:boolean }
interface Product {
  id:number
  title:string
  title_en?: string | null
  author?:string | null
  author_en?: string | null
  base_price:number
  min_price?:number|null
  max_price?:number|null
  images?:string|null
  options?:string|null
  skus:SKU[]
}
interface Review { id:number; rating:number; comment?:string|null; created_at:string }

const route = useRoute()
const product = ref<Product | null>(null)
const qty = ref(1)
const reviews = ref<Review[]>([])
const review = ref({ rating: 5, comment: '' })
const { locale, t } = useI18n()

function pickText(zh?: string | null, en?: string | null) {
  const l = String(locale.value)
  if (l === 'en') return (en || zh || '')
  return (zh || en || '')
}

function displayOptionValue(name: string, value: string) {
  // SKU/选项值：尽量只翻译常见的“版本”字段
  const l = String(locale.value)
  const key = (name || '').toLowerCase()
  if (l === 'en' && (key.includes('version') || name === '版本')) {
    if (value === '平装') return t('product.paperback')
    if (value === '精装') return t('product.hardcover')
  }
  return value
}

// 解析 options 为通用结构
const optionsMap = ref<Record<string, string[]>>({})
const optionNames = computed(() => Object.keys(optionsMap.value))
const selections = reactive<Record<string, string>>({})

const matchedSku = computed<SKU | null>(() => {
  if (!product.value) return null
  // 所有选项必须被选择
  if (optionNames.value.length > 0) {
    for (const name of optionNames.value) {
      if (!selections[name]) return null
    }
  }
  // 按 selections 完全匹配
  for (const s of product.value.skus) {
    try {
      const ov = JSON.parse(s.option_values || '{}')
      let ok = true
      for (const name of optionNames.value) {
        if (ov?.[name] !== selections[name]) { ok = false; break }
      }
      if (ok) return s
    } catch {}
  }
  return null
})

const displayPrice = computed(() => {
  const base = product.value ? Number(product.value.base_price) : 0
  const adj = matchedSku.value ? Number(matchedSku.value.price_adjustment || 0) : 0
  return (base + adj).toFixed(2)
})

const reviewCount = computed(() => reviews.value.length)
const avgRating = computed(() => {
  if (!reviews.value.length) return 0
  const sum = reviews.value.reduce((acc, r) => acc + Number(r.rating || 0), 0)
  return Number((sum / reviews.value.length).toFixed(2))
})

const canAddToCart = computed(() => {
  if (!matchedSku.value) return false
  if (!matchedSku.value.is_available) return false
  if (matchedSku.value.stock_quantity !== null && matchedSku.value.stock_quantity < 1) return false
  return true
})

const selectedImageUrl = computed(() => {
  try {
    if (!product.value?.options) return ''
    const obj = JSON.parse(product.value.options)
    const mapping = obj?.optionImages // 约定的图片映射
    if (!mapping || typeof mapping !== 'object') return ''
    // 找到第一个带有映射的选项并已选择值
    for (const name of Object.keys(mapping)) {
      const value = selections[name]
      if (value && mapping[name] && mapping[name][value]) return mapping[name][value]
    }
    return ''
  } catch { return '' }
})

async function load() {
  const id = Number(route.params.id)
  const { data } = await api.get(`/api/products/${id}`)
  product.value = data
  // 解析 options
  optionsMap.value = {}
  try {
    if (product.value?.options) {
      const obj = JSON.parse(product.value.options)
      Object.entries(obj).forEach(([k, v]) => {
        if (k === 'optionImages') return // 约定的映射键跳过
        if (Array.isArray(v)) optionsMap.value[k] = v as string[]
      })
    }
  } catch {}
  // 默认选择每个选项的第一个值
  for (const name of optionNames.value) {
    if (!selections[name] && optionsMap.value[name]?.length) {
      selections[name] = optionsMap.value[name][0]
    }
  }
  const rv = await api.get(`/api/products/${id}/reviews`)
  reviews.value = rv.data
}

async function addToCart() {
  if (!matchedSku.value) {
    ElMessage.warning(t('product.selectConfig'))
    return
  }
  try {
    await api.post('/api/cart/items', { sku_id: matchedSku.value.id, quantity: qty.value })
    ElMessage.success(t('product.addedToCart'))
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.addToCartFailed')))
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
    ElMessage.error(extractErrorMessage(e, t('msg.reviewFailed')))
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
.main-image img{ width:100%; height:260px; object-fit:cover; margin-bottom:8px; border:1px solid #eee }
</style>
