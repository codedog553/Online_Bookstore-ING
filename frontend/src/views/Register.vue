<template>
  <div class="container">
    <h2>注册</h2>
    <el-form :model="form" label-width="80px" @keyup.enter.native="onSubmit">
      <el-form-item label="姓名">
        <el-input v-model="form.full_name" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="email@example.com" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSubmit" :loading="loading">注册</el-button>
        <router-link to="/login" class="ml8">去登录</router-link>
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
const form = reactive({ full_name: '', email: '', password: '' })

async function onSubmit() {
  if (!form.full_name || !form.email || !form.password) return
  loading.value = true
  try {
    await auth.register(form.full_name, form.email, form.password)
    router.push('/products')
  } catch (e: any) {
    alert(e?.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>
.container{ max-width: 520px; margin: 24px auto; }
.ml8{ margin-left:8px }
</style>
