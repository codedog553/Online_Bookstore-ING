<template>
  <div class="container">
    <h2>登录</h2>
    <el-form :model="form" label-width="80px" @keyup.enter.native="onSubmit">
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="email@example.com" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSubmit" :loading="loading">登录</el-button>
        <router-link to="/register" class="ml8">去注册</router-link>
      </el-form-item>
    </el-form>
  </div>
</template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ email: '', password: '' })

async function onSubmit() {
  if (!form.email || !form.password) return
  loading.value = true
  try {
    await auth.login(form.email, form.password)
    router.push('/products')
  } catch (e: any) {
    alert(e?.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>
.container{ max-width: 520px; margin: 24px auto; }
.ml8{ margin-left:8px }
</style>
