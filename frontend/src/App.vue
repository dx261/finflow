<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
function retry(): void {
  window.location.reload()
}
</script>

<template>
  <div v-if="auth.startupError" class="startup-error">
    <el-alert title="无法连接系统，请确认后端和数据库已启动" type="error" :closable="false">
      {{ auth.startupError }}
    </el-alert>
    <el-button type="primary" @click="retry">重新连接</el-button>
  </div>
  <router-view v-else />
</template>

<style scoped>
.startup-error {
  max-width: 600px;
  margin: 15vh auto;
  padding: 24px;
  display: grid;
  gap: 16px;
}
</style>
