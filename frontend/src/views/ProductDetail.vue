<template>
  <div v-if="product">
    <el-row :gutter="20">
      <el-col :span="10">
        <ProductImageGallery
          :photos-by-sku="photosBySku"
          :selected-sku-id="matchedSku ? matchedSku.id : null"
          :alt="pickText(product.title, product.title_en)"
        />
      </el-col>
      <el-col :span="14">
        <div class="detail-panel">
          <h2>{{ pickText(product.title, product.title_en) }}</h2>
          <p class="meta-text" v-if="pickText(product.author, product.author_en)">
            {{ t('product.author') }}：{{ pickText(product.author, product.author_en) }}
          </p>
          <p class="meta-text" v-if="pickText(product.publisher, product.publisher_en)">
            {{ t('product.publisher') }}：{{ pickText(product.publisher, product.publisher_en) }}
          </p>
          <div class="price">￥{{ displayPrice }}</div>

          <div class="mt16" v-if="reviewSummary.rating_count > 0">
            <el-rate :model-value="reviewSummary.average_rating" disabled show-score />
            <span class="review-count">({{ reviewSummary.rating_count }})</span>
          </div>

          <div v-for="name in optionNames" :key="name" class="mt16">
            <span class="option-label">{{ displayOptionKey(name) }}：</span>
            <el-select v-model="selections[name]" :placeholder="t('product.select')" style="width:180px">
              <el-option v-for="v in optionsMap[name]" :key="v" :label="displayOptionValue(name, v)" :value="v" />
            </el-select>
          </div>

          <div class="mt16">
            <span class="option-label">{{ t('product.quantity') }}：</span>
            <el-input-number v-model="qty" :min="1" />
            <span v-if="matchedSku && matchedSku.stock_quantity !== null" class="stock-text">
              {{ t('product.stock') }}：{{ matchedSku.stock_quantity }}
            </span>
          </div>

          <div class="mt16">
            <el-button type="primary" @click="addToCart" :disabled="!canAddToCart">{{ t('product.addToCart') }}</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="detail-section mt24">
      <h3>{{ t('product.description') }}</h3>
      <div class="description-text">
        {{ pickText(product.description, product.description_en) || t('msg.noText') }}
      </div>
    </div>

    <div class="detail-section mt24">
      <div class="review-header">
        <h3>{{ t('product.reviews') }}</h3>
        <div class="review-sorter">
          <span>{{ t('product.reviewSort') }}：</span>
          <el-radio-group v-model="commentSort" size="small" @change="loadReviews">
            <el-radio-button label="likes">{{ t('product.sortByLikes') }}</el-radio-button>
            <el-radio-button label="time">{{ t('product.sortByTime') }}</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div class="review-summary-grid mb16">
        <div class="summary-card">
          <div class="summary-label">{{ t('product.ratings') }}</div>
          <div class="summary-value">{{ reviewSummary.rating_count }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">{{ t('product.comments') }}</div>
          <div class="summary-value">{{ reviewSummary.comment_count }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">{{ t('product.myRatingQuota') }}</div>
          <div class="summary-value">{{ reviewSummary.my_rating_quota }}</div>
        </div>
      </div>

      <div class="review-forms mb16">
        <el-card class="review-card">
          <template #header>{{ t('product.submitRating') }}</template>
          <el-form label-width="110px">
            <el-form-item :label="t('product.rating')">
              <el-rate v-model="ratingForm.rating" :max="5" />
            </el-form-item>
            <el-form-item :label="t('product.ratingOrder')">
              <el-select v-model="ratingForm.order_id" :placeholder="t('product.ratingOrder')" style="width:100%" :disabled="reviewSummary.my_rating_quota < 1">
                <el-option v-for="orderId in availableRatingOrders" :key="orderId" :label="orderId" :value="orderId" />
              </el-select>
            </el-form-item>
            <div v-if="reviewSummary.my_rating_quota < 1" class="helper-text">{{ t('product.noRatingQuota') }}</div>
            <el-form-item>
              <el-button type="primary" @click="submitRating" :disabled="reviewSummary.my_rating_quota < 1">{{ t('product.submitRating') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card class="review-card">
          <template #header>{{ t('product.submitComment') }}</template>
          <div class="helper-text mb12">{{ t('product.canComment') }}</div>
          <el-input type="textarea" v-model="commentForm.content" :rows="4" />
          <div class="mt16">
            <el-button type="primary" @click="submitComment">{{ t('product.submitComment') }}</el-button>
          </div>
        </el-card>
      </div>

      <el-empty v-if="comments.length === 0" :description="t('product.noComments')" />
      <div v-else class="comment-list">
        <div v-for="comment in comments" :key="comment.id" class="comment-card">
          <div class="comment-head">
            <strong>{{ comment.user_name }}</strong>
            <span class="comment-time">{{ formatDate(comment.created_at) }}</span>
          </div>
          <div class="comment-text">{{ comment.content }}</div>
          <div class="comment-actions">
            <span>{{ t('product.likes') }}: {{ comment.like_count }}</span>
            <el-button link type="primary" :disabled="comment.liked_by_me" @click="likeComment(comment.id)">{{ t('product.like') }}</el-button>
            <el-button link @click="toggleReply(comment.id)">{{ t('product.reply') }}</el-button>
          </div>
          <div v-if="replyingCommentId === comment.id" class="reply-box">
            <el-input type="textarea" v-model="replyDrafts[comment.id]" :rows="3" />
            <div class="mt12">
              <el-button size="small" type="primary" @click="submitReply(comment.id)">{{ t('product.replyComment') }}</el-button>
            </div>
          </div>
          <div v-if="comment.replies.length" class="reply-list">
            <div v-for="reply in comment.replies" :key="reply.id" class="reply-item">
              <div class="comment-head">
                <strong>{{ reply.user_name }}</strong>
                <span class="comment-time">{{ formatDate(reply.created_at) }}</span>
              </div>
              <div class="comment-text">{{ reply.content }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <el-empty v-else :description="t('msg.loading')" />
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/http'
import ProductImageGallery from '../components/ProductImageGallery.vue'
import { extractErrorMessage } from '../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { fallbackVersionToEnglish, pickProductText, translateOptionValue } from '../utils/productI18n'

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
interface ReviewSummary { average_rating:number; rating_count:number; comment_count:number; my_rating_quota:number; can_comment:boolean; available_rating_orders:string[] }
interface RatingItem { id:number; order_id:string; rating:number; created_at:string }
interface ReplyItem { id:number; user_name:string; content:string; created_at:string }
interface CommentItem { id:number; user_name:string; content:string; created_at:string; like_count:number; liked_by_me:boolean; replies: ReplyItem[] }
interface ReviewPage { summary: ReviewSummary; ratings: RatingItem[]; comments: CommentItem[] }

const route = useRoute()
const product = ref<Product | null>(null)
const qty = ref(1)
const ratings = ref<RatingItem[]>([])
const comments = ref<CommentItem[]>([])
const reviewSummary = ref<ReviewSummary>({ average_rating: 0, rating_count: 0, comment_count: 0, my_rating_quota: 0, can_comment: false, available_rating_orders: [] })
const ratingForm = reactive({ order_id: '', rating: 5 })
const commentForm = reactive({ content: '' })
const replyDrafts = reactive<Record<number, string>>({})
const replyingCommentId = ref<number | null>(null)
const commentSort = ref<'likes' | 'time'>('likes')
const { t, locale } = useI18n()

function pickText(zh?: string | null, en?: string | null) {
  return pickProductText(zh, en, String(locale.value))
}

function displayOptionValue(name: string, value: string) {
  return translateOptionValue(name, value, product.value?.options || null, String(locale.value))
}

function displayOptionKey(name: string): string {
  const key = (name || '').toLowerCase()
  if (key.includes('version') || name === '版本') return t('product.version')
  return name
}

const optionsMap = ref<Record<string, string[]>>({})
const optionNames = computed(() => Object.keys(optionsMap.value))
const selections = reactive<Record<string, string>>({})

const matchedSku = computed<SKU | null>(() => {
  if (!product.value) return null
  if (optionNames.value.length > 0) {
    for (const name of optionNames.value) {
      if (!selections[name]) return null
    }
  }
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

const canAddToCart = computed(() => {
  if (!matchedSku.value) return false
  if (!matchedSku.value.is_available) return false
  if (matchedSku.value.stock_quantity !== null && matchedSku.value.stock_quantity < 1) return false
  return true
})

const photosBySku = ref<Record<string, string[]>>({})
const availableRatingOrders = computed(() => reviewSummary.value.available_rating_orders || [])

async function loadReviews() {
  const id = Number(route.params.id)
  const { data } = await api.get<ReviewPage>(`/api/products/${id}/reviews`, { params: { sort: commentSort.value } })
  reviewSummary.value = data.summary
  ratings.value = data.ratings
  comments.value = data.comments
}

async function load() {
  const id = Number(route.params.id)
  const { data } = await api.get(`/api/products/${id}`)
  product.value = data

  try {
    const { data: photoData } = await api.get(`/api/products/${id}/photos`)
    photosBySku.value = photoData?.by_sku || {}
  } catch {
    photosBySku.value = {}
  }

  optionsMap.value = {}
  try {
    if (product.value?.options) {
      const obj = JSON.parse(product.value.options)
      Object.entries(obj).forEach(([k, v]) => {
        if (k === 'optionImages' || k === 'optionValueI18n') return
        if (Array.isArray(v)) optionsMap.value[k] = v as string[]
      })
    }
  } catch {}

  for (const name of optionNames.value) {
    if (selections[name] === undefined) selections[name] = ''
  }
  await loadReviews()
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

async function submitRating() {
  const id = Number(route.params.id)
  if (!ratingForm.order_id) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }
  try {
    await api.post(`/api/products/${id}/ratings`, ratingForm)
    ratingForm.order_id = ''
    ratingForm.rating = 5
    await loadReviews()
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.ratingFailed')))
  }
}

async function submitComment() {
  const id = Number(route.params.id)
  if (!commentForm.content.trim()) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }
  try {
    await api.post(`/api/products/${id}/comments`, { content: commentForm.content })
    commentForm.content = ''
    await loadReviews()
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.commentFailed')))
  }
}

function toggleReply(commentId: number) {
  replyingCommentId.value = replyingCommentId.value === commentId ? null : commentId
}

async function submitReply(commentId: number) {
  const id = Number(route.params.id)
  const content = (replyDrafts[commentId] || '').trim()
  if (!content) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }
  try {
    await api.post(`/api/products/${id}/comments/${commentId}/replies`, { content })
    replyDrafts[commentId] = ''
    replyingCommentId.value = null
    await loadReviews()
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.replyFailed')))
  }
}

async function likeComment(commentId: number) {
  const id = Number(route.params.id)
  try {
    await api.post(`/api/products/${id}/comments/${commentId}/like`)
    await loadReviews()
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.likeFailed')))
  }
}

function formatDate(s:string){
  try { return new Date(s).toLocaleString() } catch { return s }
}

onMounted(load)
</script>

<style scoped>
.detail-panel{ padding: 18px; background: #ffffff; border:1px solid var(--el-border-color-light); border-radius:12px; box-shadow: 0 6px 18px rgba(24,52,110,0.08); }
.meta-text{ color: var(--el-text-color-secondary); margin: 6px 0; }
.price{ color: var(--brand-600); font-size:22px; margin-top:8px; font-weight:700 }
.review-count{ margin-left:8px; color: var(--el-text-color-secondary); }
.option-label{ color: var(--brand-800); font-weight: 600; }
.stock-text{ margin-left:8px; color: var(--el-text-color-secondary); }
.detail-section{ padding: 16px; background: #ffffff; border:1px solid var(--el-border-color-light); border-radius:12px; box-shadow: 0 6px 18px rgba(24,52,110,0.06); }
.description-text{ white-space: pre-wrap; color: #3c4a66; line-height: 1.7; }
.mt16{ margin-top:16px }
.mt24{ margin-top:24px }
.mt12{ margin-top:12px }
.mb16{ margin-bottom:16px }
.mb12{ margin-bottom:12px }
.review-header{ display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap }
.review-sorter{ display:flex; align-items:center; gap:10px }
.review-summary-grid{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px }
.summary-card{ padding:14px; border:1px solid var(--el-border-color-light); border-radius:12px; background:#f8fbff }
.summary-label{ color:#6b7280; font-size:13px }
.summary-value{ font-size:24px; font-weight:700; color:var(--brand-700) }
.review-forms{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:16px }
.review-card{ height:100% }
.helper-text{ color:#6b7280; line-height:1.6 }
.comment-list{ display:flex; flex-direction:column; gap:16px }
.comment-card{ padding:16px; border:1px solid var(--el-border-color-light); border-radius:12px; background:#fcfdff }
.comment-head{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:8px }
.comment-time{ color:#8a94a6; font-size:13px }
.comment-text{ white-space:pre-wrap; line-height:1.7; color:#334155 }
.comment-actions{ display:flex; gap:12px; align-items:center; margin-top:10px }
.reply-box{ margin-top:12px }
.reply-list{ margin-top:14px; padding-top:12px; border-top:1px dashed var(--el-border-color) }
.reply-item{ padding:10px 12px; background:#f7f9fc; border-radius:10px; margin-top:8px }
@media (max-width: 900px){
  .review-summary-grid,.review-forms{ grid-template-columns:1fr }
}
</style>
