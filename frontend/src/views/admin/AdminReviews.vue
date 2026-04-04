<template>
  <div>
    <h2>{{ t('admin.reviewsTitle') }}</h2>

    <el-card class="mb16">
      <el-form :inline="true" :model="query" @submit.prevent>
        <el-form-item :label="t('admin.keyword')">
          <el-input v-model="query.q" :placeholder="t('admin.keyword')" style="width:240px" @keyup.enter="load" />
        </el-form-item>
        <el-form-item :label="t('admin.visible')">
          <el-select v-model="query.visible" style="width:160px">
            <el-option :label="t('admin.visible')" :value="true" />
            <el-option :label="t('admin.hidden')" :value="false" />
            <el-option :label="t('admin.all')" :value="null" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">{{ t('admin.search') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="list" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" :label="t('admin.id')" width="80" />
      <el-table-column prop="user_email" :label="t('auth.email')" width="220" />
      <el-table-column prop="product_title" :label="t('admin.title')" />
      <el-table-column prop="rating" :label="t('product.rating')" width="100" />
      <el-table-column :label="t('product.comment')">
        <template #default="{ row }">
          <div style="white-space: pre-wrap">{{ row.comment || '-' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="is_visible" :label="t('admin.visible')" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.is_visible" type="success">{{ t('admin.visible') }}</el-tag>
          <el-tag v-else type="info">{{ t('admin.hidden') }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('order.createdAt')" width="200">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('admin.operations')" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="toggleVisible(row)">
            {{ row.is_visible ? t('admin.hidden') : t('admin.visible') }}
          </el-button>
          <el-popconfirm :title="t('admin.delete') + '?'" @confirm="del(row)">
            <template #reference>
              <el-button size="small" type="danger">{{ t('admin.delete') }}</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '../../api/http'
import { extractErrorMessage } from '../../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

interface AdminReview {
  id: number
  user_id: number
  user_email: string
  product_id: number
  product_title: string
  order_id: string
  rating: number
  comment?: string | null
  is_visible: boolean
  created_at: string
}

const { t } = useI18n()
const list = ref<AdminReview[]>([])
const loading = ref(false)
const query = ref<{ q: string; visible: boolean | null }>({ q: '', visible: null })

function formatDate(s: string) {
  try {
    return new Date(s).toLocaleString()
  } catch {
    return s
  }
}

async function load() {
  loading.value = true
  try {
    const params: any = {}
    if (query.value.q) params.q = query.value.q
    if (query.value.visible !== null) params.visible = query.value.visible
    const { data } = await api.get('/api/admin/reviews', { params })
    list.value = data
  } catch (e: any) {
    ElMessage.error(extractErrorMessage(e, t('msg.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function toggleVisible(row: AdminReview) {
  try {
    const { data } = await api.patch(`/api/admin/reviews/${row.id}`, { is_visible: !row.is_visible })
    row.is_visible = data.is_visible
    ElMessage.success(t('admin.updated'))
  } catch (e: any) {
    ElMessage.error(extractErrorMessage(e, t('msg.updateFailed')))
  }
}

async function del(row: AdminReview) {
  try {
    await api.delete(`/api/admin/reviews/${row.id}`)
    ElMessage.success(t('admin.deleted'))
    await load()
  } catch (e: any) {
    ElMessage.error(extractErrorMessage(e, t('msg.deleteFailed')))
  }
}

onMounted(load)
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
}
</style>
