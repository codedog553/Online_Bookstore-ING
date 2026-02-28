<template>
  <div>
    <el-carousel height="260px" v-if="imgs.length > 0">
      <el-carousel-item v-for="(img, idx) in imgs" :key="idx">
        <img :src="img" alt="图片" style="width:100%;height:260px;object-fit:cover" />
      </el-carousel-item>
    </el-carousel>
    <div v-else style="height:260px;display:flex;align-items:center;justify-content:center;border:1px solid #eee;color:#888">
      无图片
    </div>
  </div>
</template>
<script setup lang="ts">
const props = defineProps<{ images?: string | null }>()
let imgs: string[] = []
try {
  if (props.images) {
    const val = JSON.parse(props.images)
    if (Array.isArray(val)) imgs = val
  }
} catch (e) {
  imgs = []
}
</script>
