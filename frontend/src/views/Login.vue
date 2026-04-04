<template>
  <div class="container">
    <h2>{{ t('auth.loginTitle') }}</h2>
    <el-form :model="form" label-width="80px" @keyup.enter.native="onSubmit">
      <el-form-item :label="t('auth.email')">
        <el-input v-model="form.email" placeholder="email@example.com" />
      </el-form-item>
      <el-form-item :label="t('auth.password')">
        <el-input v-model="form.password" type="password" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSubmit" :loading="loading">{{ t('auth.loginTitle') }}</el-button>
        <router-link to="/register" class="ml8">{{ t('auth.toRegister') }}</router-link>
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
const form = reactive({ email: '', password: '' })
const { t } = useI18n()

async function onSubmit() {
  if (!form.email || !form.password) return
  loading.value = true
  try {
    await auth.login(form.email, form.password)
    router.push('/products')
  } catch (e: any) {
    ElMessage.error(extractErrorMessage(e, t('msg.loginFailed')))
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>
.container{ max-width: 520px; margin: 32px auto; padding: 24px 26px; background:#ffffff; border:1px solid var(--el-border-color-light); border-radius:12px; box-shadow: 0 10px 24px rgba(24,52,110,0.08); }
.ml8{ margin-left:8px }
</style>
