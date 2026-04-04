<template>
  <div>
    <el-carousel height="260px" v-if="imgs.length > 0">
      <el-carousel-item v-for="(img, idx) in imgs" :key="idx">
        <img :src="img" :alt="alt || 'Image'" style="width:100%;height:260px;object-fit:cover" />
      </el-carousel-item>
    </el-carousel>
    <div v-else style="height:260px;display:flex;align-items:center;justify-content:center;border:1px solid #eee;color:#888">
      {{ t('msg.noImage') }}
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { resolveBackendUrl } from '../utils/resolveUrl'

type ImagesProp = string | string[] | null | undefined

const props = defineProps<{ images?: ImagesProp; alt?: string }>()
const { t } = useI18n()

const imgs = computed<string[]>(() => {
  const v = props.images
  if (!v) return []
  if (Array.isArray(v)) return v.map((x) => resolveBackendUrl(String(x))).filter(Boolean)

  // string: support either JSON array string or a single URL string
  const s = String(v).trim()
  if (!s) return []
  try {
    const parsed = JSON.parse(s)
    if (Array.isArray(parsed)) return parsed.map((x) => resolveBackendUrl(String(x))).filter(Boolean)
  } catch {
    // not JSON
  }
  return [resolveBackendUrl(s)].filter(Boolean)
})
</script>
