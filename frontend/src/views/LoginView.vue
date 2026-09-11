<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/api/client'

const auth = useAuthStore()
const router = useRouter()

const mode = ref<'login' | 'register'>('login')
const login = ref('')
const username = ref('')
const email = ref('')
const password = ref('')
const loading = ref(false)

async function submit(): Promise<void> {
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(login.value, password.value)
      ElMessage.success('登录成功')
    } else {
      await auth.register(username.value, email.value, password.value)
      ElMessage.success('注册成功，请登录')
      mode.value = 'login'
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function switchMode(): void {
  mode.value = mode.value === 'login' ? 'register' : 'login'
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <div class="login-title">FinFlow</div>
      <div class="login-subtitle">个人多账户资金管理平台</div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item v-if="mode === 'login'" label="用户名 / 邮箱" required>
          <el-input v-model="login" placeholder="用户名或邮箱" autocomplete="username" />
        </el-form-item>
        <template v-else>
          <el-form-item label="用户名" required>
            <el-input v-model="username" placeholder="3-50 个字符" autocomplete="username" />
          </el-form-item>
          <el-form-item label="邮箱" required>
            <el-input v-model="email" placeholder="you@example.com" autocomplete="email" />
          </el-form-item>
        </template>
        <el-form-item label="密码" required>
          <el-input
            v-model="password"
            type="password"
            show-password
            placeholder="至少 8 位"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button
          type="primary"
          native-type="submit"
          class="submit-btn"
          :loading="loading"
        >
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </el-form>

      <el-button link type="primary" class="switch-btn" @click="switchMode">
        {{ mode === 'login' ? '没有账号？注册' : '已有账号？登录' }}
      </el-button>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: linear-gradient(135deg, #1f2d3d 0%, #2c3e50 100%);
}
.login-card {
  width: 380px;
  padding: 12px;
}
.login-title {
  font-size: 26px;
  font-weight: 700;
  text-align: center;
  color: #1f2d3d;
}
.login-subtitle {
  text-align: center;
  color: #909399;
  margin-bottom: 24px;
}
.submit-btn {
  width: 100%;
}
.switch-btn {
  width: 100%;
  margin-top: 8px;
}
</style>
