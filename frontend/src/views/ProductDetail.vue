<template>
  <div v-if="product">
    <el-row :gutter="20">
      <el-col :span="10">
        <ImageCarousel :images="carouselImages" :alt="pickText(product.title, product.title_en)" />
      </el-col>
      <el-col :span="14">
        <h2>{{ pickText(product.title, product.title_en) }}</h2>
        <p style="color:#666" v-if="pickText(product.author, product.author_en)">
          {{ t('product.author') }}：{{ pickText(product.author, product.author_en) }}
        </p>
        <p style="color:#666" v-if="pickText(product.publisher, product.publisher_en)">
          {{ t('product.publisher') }}：{{ pickText(product.publisher, product.publisher_en) }}
        </p>
        <div class="price">￥{{ displayPrice }}</div>

        <div class="mt16" v-if="reviewCount > 0">
          <el-rate :model-value="avgRating" disabled show-score />
          <span style="margin-left:8px;color:#666">({{ reviewCount }})</span>
        </div>

        <div v-for="name in optionNames" :key="name" class="mt16">
          <span>{{ displayOptionKey(name) }}：</span>
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
      <h3>{{ t('product.description') }}</h3>
      <div style="white-space: pre-wrap; color:#444">
        {{ pickText(product.description, product.description_en) || t('msg.noText') }}
      </div>

      <div class="mt24"></div>
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
import { fallbackVersionToEnglish, getOptionValueI18n, pickProductText, translateOptionValue } from '../utils/productI18n'

// =========================
// Requirements Traceability
// =========================
// A2: 商品详情页允许未登录访问；但“加入购物车”调用 /api/cart 会在未登录时被后端拒绝并提示。
// A6: 展示商品详情的额外属性（作者/出版方/描述等）。
// A7: 支持加入购物车（默认 qty=1）。
// B1: 多图展示：图片来自每个 SKU 的 photos 列表（本地上传）。
// D1/D2: 可配置商品：必须选择每个 option 才能匹配到 SKU。
// D4/D5: SKU 有库存与可售状态；缺货/不可售时禁止加入购物车并提示。
// W2: 商品信息双语字段按规则显示（pickProductText/translateOptionValue）。

interface SKU { id:number; option_values:string; price_adjustment:number; stock_quantity:number; is_available:boolean }
interface Product {
  id:number
  title:string
  title_en?: string | null
  author?:string | null
  author_en?: string | null
  publisher?: string | null
  publisher_en?: string | null
  base_price:number
  min_price?:number|null
  max_price?:number|null
  options?:string|null
  description?: string | null
  description_en?: string | null
  skus:SKU[]
}
interface Review { id:number; rating:number; comment?:string|null; created_at:string }

const route = useRoute()
const product = ref<Product | null>(null)
const qty = ref(1)
const reviews = ref<Review[]>([])
const review = ref({ rating: 5, comment: '' })
const { t, locale } = useI18n()
function pickText(zh?: string | null, en?: string | null) {
  return pickProductText(zh, en, String(locale.value))
}

function pickVersionLabel(v: string) {
  // 当前项目的 version 值是中文（平装/精装等），在非中文语言下做一个兜底翻译
  const l = String(locale.value)
  if (l === 'zh' || l === 'zh-TW') return v
  return fallbackVersionToEnglish(v)
}

function displayOptionValue(name: string, value: string) {
  // W2: non-zh locales should use English for product info, including option values.
  // Prefer vendor-provided mapping in product.options.optionValueI18n, fallback to common version translation.
  return translateOptionValue(name, value, product.value?.options || null, String(locale.value))
}

function displayOptionKey(name: string): string {
  const key = (name || '').toLowerCase()
  if (key.includes('version') || name === '版本') return t('product.version')
  return name
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
  // D5: 缺货/不可售 SKU 不可加入购物车。
  if (!matchedSku.value) return false
  if (!matchedSku.value.is_available) return false
  if (matchedSku.value.stock_quantity !== null && matchedSku.value.stock_quantity < 1) return false
  return true
})
const photosBySku = ref<Record<string, string[]>>({})

const carouselImages = computed(() => {
  // B1: show selected SKU's photos if available; else fallback to ANY sku photos
  const skuId = matchedSku.value?.id
  if (skuId != null) {
    const list = photosBySku.value?.[String(skuId)]
    if (Array.isArray(list) && list.length) return list
  }
  // fallback to first available sku photos
  try {
    const bySku = photosBySku.value || {}
    for (const k of Object.keys(bySku)) {
      const list = bySku[k]
      if (Array.isArray(list) && list.length) return list
    }
  } catch {}
  return null
})

async function load() {
  const id = Number(route.params.id)
  const { data } = await api.get(`/api/products/${id}`)
  product.value = data

  // 加载 SKU 图片映射（B1/D2）
  try {
    const { data: photoData } = await api.get(`/api/products/${id}/photos`)
    photosBySku.value = photoData?.by_sku || {}
  } catch {
    photosBySku.value = {}
  }

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
  // D2: 不自动选择，要求用户显式选择每个选项。
  // （simple product 通常没有 optionNames；matchedSku 会自动匹配默认 SKU）
  for (const name of optionNames.value) {
    if (selections[name] === undefined) selections[name] = ''
  }
  const rv = await api.get(`/api/products/${id}/reviews`)
  reviews.value = rv.data
}

async function addToCart() {
  // A7/D2: 加购必须是“已选中配置后的 SKU”。
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
</style>
