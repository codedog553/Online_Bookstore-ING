<template>
  <div class="container">
    <h2>{{ t('auth.registerTitle') }}</h2>
    <el-form :model="form" label-width="90px" @keyup.enter.native="onSubmit">
      <el-form-item :label="t('auth.fullName')">
        <el-input v-model="form.full_name" />
      </el-form-item>
      <el-form-item :label="t('auth.email')">
        <el-input v-model="form.email" placeholder="email@example.com" />
      </el-form-item>
      <el-form-item :label="t('auth.password')">
        <el-input v-model="form.password" type="password" :placeholder="t('auth.passwordHint')" />
        <div style="color:#888;font-size:12px;margin-top:4px">{{ t('auth.passwordHint') }}</div>
      </el-form-item>

      <h3 style="margin: 12px 0">{{ t('order.address') }}</h3>
      <el-form-item :label="t('order.receiverName')"><el-input v-model="form.receiver_name" /></el-form-item>
      <el-form-item :label="t('order.phone')"><el-input v-model="form.phone" /></el-form-item>
      <el-form-item :label="t('order.province')"><el-input v-model="form.province" /></el-form-item>
      <el-form-item :label="t('order.city')"><el-input v-model="form.city" /></el-form-item>
      <el-form-item :label="t('order.district')"><el-input v-model="form.district" /></el-form-item>
      <el-form-item :label="t('order.detailAddress')"><el-input v-model="form.detail_address" /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSubmit" :loading="loading">{{ t('auth.registerTitle') }}</el-button>
        <router-link to="/login" class="ml8">{{ t('auth.toLogin') }}</router-link>
      </el-form-item>
    </el-form>
  </div>
</template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { extractErrorMessage } from '../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({
  full_name: '',
  email: '',
  password: '',
  receiver_name: '',
  phone: '',
  province: '',
  city: '',
  district: '',
  detail_address: '',
})
const { t } = useI18n()

async function onSubmit() {
  if (!form.full_name || !form.email || !form.password) return
  if (!form.receiver_name || !form.province || !form.city || !form.district || !form.detail_address) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }
  loading.value = true
  try {
    await auth.register(form.full_name, form.email, form.password, {
      receiver_name: form.receiver_name,
      phone: form.phone || undefined,
      province: form.province,
      city: form.city,
      district: form.district,
      detail_address: form.detail_address,
    })
    router.push('/products')
  } catch (e: any) {
    ElMessage.error(extractErrorMessage(e, t('msg.registerFailed')))
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>
.container{ max-width: 520px; margin: 24px auto; }
.ml8{ margin-left:8px }
</style>
