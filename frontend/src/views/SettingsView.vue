<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const profile = computed(() => auth.user)
</script>

<template>
  <el-card>
    <template #header>账户设置</template>

    <el-descriptions v-if="profile" :column="1" border>
      <el-descriptions-item label="用户名">{{ profile.username }}</el-descriptions-item>
      <el-descriptions-item label="邮箱">{{ profile.email }}</el-descriptions-item>
      <el-descriptions-item label="角色">
        <el-tag :type="profile.role === 'OWNER' ? 'warning' : 'info'">{{ profile.role }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="注册时间">{{
        profile.created_at?.replace('T', ' ').slice(0, 19)
      }}</el-descriptions-item>
    </el-descriptions>

    <el-divider />

    <el-alert type="info" :closable="false">
      <p>
        <b>FinFlow 安全边界</b
        >：系统只做资金规划、分配建议、对账确认，绝不直接操作真实银行账户。所有真实资金操作均由你在银行端人工完成。
      </p>
      <p>金额一律以 Decimal 精确处理，不使用浮点数。</p>
    </el-alert>
  </el-card>
</template>
