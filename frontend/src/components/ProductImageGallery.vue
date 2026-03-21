<template>
  <div class="gallery">
    <!--
      B1: 商品多图展示。
      - 大图：等比例完整展示（contain），可点击进入 el-image viewer。
      - 缩略图：展示该商品下所有 SKU 的所有图片；手动水平滚动；点击切换并高亮。
      - 轮播：未选中 SKU 时轮播全商品图；选中 SKU 后轮播该 SKU 图。
    -->

    <div class="main">
      <el-image
        v-if="displayImage"
        class="mainImage"
        :src="displayImage"
        :alt="alt || 'Image'"
        fit="contain"
        :preview-src-list="previewImages"
        :initial-index="previewInitialIndex"
        preview-teleported
      />

      <div v-else class="empty">
        {{ t('msg.noImage') }}
      </div>
    </div>

    <div v-if="thumbImages.length" class="thumbBar" :aria-label="t('msg.images')">
      <div
        v-for="(img, idx) in thumbImages"
        :key="`${idx}-${img}`"
        class="thumb"
        :class="{ active: img === currentImage }"
        @click="() => selectThumb(img)"
      >
        <img :src="img" :alt="alt || 'thumb'" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { resolveBackendUrl } from '../utils/resolveUrl'

// =========================
// Requirements Traceability
// =========================
// B1: 商品多图（每个 SKU 多张）。
// D2: 选择配置后切换到对应 SKU 的图片组。

const props = defineProps<{
  photosBySku: Record<string, string[]>
  selectedSkuId: number | null
  alt?: string
  // 自动轮播间隔（ms）
  intervalMs?: number
}>()

const { t } = useI18n()

function normalizeList(v: any): string[] {
  if (!Array.isArray(v)) return []
  return v
    .map((x) => resolveBackendUrl(String(x)))
    .map((x) => String(x || '').trim())
    .filter(Boolean)
}

const thumbImages = computed<string[]>(() => {
  // 该商品下所有 SKU 的所有图片，flatten + 去重（按 url 字符串）
  const set = new Set<string>()
  const bySku = props.photosBySku || {}
  for (const k of Object.keys(bySku)) {
    for (const p of normalizeList(bySku[k])) set.add(p)
  }
  return Array.from(set)
})

const selectedSkuImages = computed<string[]>(() => {
  const id = props.selectedSkuId
  if (id == null) return []
  const list = props.photosBySku?.[String(id)]
  return normalizeList(list)
})

const rotateImages = computed<string[]>(() => {
  // 未选择 SKU：轮播全商品图；选择 SKU：轮播该 SKU 图
  if (selectedSkuImages.value.length) return selectedSkuImages.value
  return thumbImages.value
})

const currentImage = ref<string>('')
let timer: any = null

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function startTimer() {
  stopTimer()
  const list = rotateImages.value
  if (!list.length) return
  const ms = Number(props.intervalMs || 2600)
  if (list.length <= 1) return

  timer = setInterval(() => {
    const idx = list.findIndex((x) => x === currentImage.value)
    const next = idx < 0 ? 0 : (idx + 1) % list.length
    currentImage.value = list[next]
  }, ms)
}

function ensureCurrentImage() {
  const list = rotateImages.value
  if (!list.length) {
    currentImage.value = ''
    return
  }
  if (!currentImage.value || !list.includes(currentImage.value)) {
    currentImage.value = list[0]
  }
}

function selectThumb(img: string) {
  currentImage.value = img
  // 用户手动选择时重启轮播，从选中图继续
  startTimer()
}

const displayImage = computed(() => currentImage.value)

const previewImages = computed(() => {
  // viewer 里展示全商品图，便于在大图预览中直接切换到其它版本的图
  return thumbImages.value
})

const previewInitialIndex = computed(() => {
  const idx = previewImages.value.findIndex((x) => x === currentImage.value)
  return idx >= 0 ? idx : 0
})

watch(
  () => [props.selectedSkuId, props.photosBySku],
  () => {
    // SKU 切换 / 图片更新：重置当前图到新的轮播集合第一张
    currentImage.value = ''
    ensureCurrentImage()
    startTimer()
  },
  { deep: true }
)

watch(
  rotateImages,
  () => {
    ensureCurrentImage()
    startTimer()
  },
  { deep: true }
)

onMounted(() => {
  ensureCurrentImage()
  startTimer()
})

onBeforeUnmount(() => {
  stopTimer()
})
</script>

<style scoped>
.gallery {
  width: 100%;
}

.main {
  width: 100%;
  /*
    需求：自适应容器高度，尽可能展示完整图片。
    clamp(min, preferred, max)
  */
  height: clamp(260px, 45vh, 560px);
  border: 1px solid #eee;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}

.mainImage {
  width: 100%;
  height: 100%;
}

.empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #888;
}

.thumbBar {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.thumb {
  width: 64px;
  height: 64px;
  flex: 0 0 auto;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  background: #fafafa;
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb.active {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

/* 移动端略微调小缩略图 */
@media (max-width: 768px) {
  .thumb {
    width: 56px;
    height: 56px;
  }
}
</style>
