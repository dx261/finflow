<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const navItems = [
  { path: '/dashboard', icon: 'Odometer', label: '仪表盘' },
  { path: '/accounts', icon: 'Wallet', label: '账户' },
  { path: '/transactions', icon: 'List', label: '交易' },
  { path: '/payments', icon: 'Calendar', label: '付款' },
  { path: '/reconciliation', icon: 'Checked', label: '对账' },
  { path: '/forecast', icon: 'TrendCharts', label: '现金流预测' },
  { path: '/audit', icon: 'Document', label: '审计' },
  { path: '/settings', icon: 'Setting', label: '设置' },
]

const activeMenu = computed(() => route.path)

function logout(): void {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="app-aside">
      <div class="brand">
        <span class="brand-mark">F</span>
        <span class="brand-name">FinFlow</span>
      </div>
      <el-menu :default-active="activeMenu" router class="app-menu">
        <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-title">{{ route.meta.title }}</div>
        <div class="header-right">
          <el-tag size="small" :type="auth.user?.role === 'OWNER' ? 'warning' : 'info'">
            {{ auth.user?.role }}
          </el-tag>
          <span class="username">{{ auth.displayName }}</span>
          <el-button size="small" @click="logout">退出</el-button>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100vh;
}
.app-aside {
  background: #1f2d3d;
  color: #fff;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 18px 20px;
  color: #fff;
  font-weight: 600;
  font-size: 18px;
}
.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: #409eff;
  color: #fff;
}
.app-menu {
  border-right: none;
  background: transparent;
  --el-menu-text-color: #c0c4cc;
  --el-menu-hover-bg-color: #283747;
}
.app-menu :deep(.el-menu-item.is-active) {
  color: #fff;
}
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-light);
  background: #fff;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.app-main {
  background: #f5f7fa;
  overflow: auto;
}
</style>
