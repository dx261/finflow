<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { AuditLog } from '@/types'

const logs = ref<AuditLog[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await api.get<AuditLog[]>('/audit')
    logs.value = res.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
})

function fmtData(value: unknown): string {
  if (value == null) return '-'
  return JSON.stringify(value).slice(0, 200)
}
</script>

<template>
  <el-card>
    <template #header>审计日志</template>
    <el-table v-loading="loading" :data="logs" size="small">
      <el-table-column prop="created_at" label="时间" width="180">
        <template #default="{ row }">{{ row.created_at?.replace('T', ' ').slice(0, 19) }}</template>
      </el-table-column>
      <el-table-column prop="action" label="操作" width="180" />
      <el-table-column prop="resource_type" label="资源" width="100" />
      <el-table-column prop="resource_id" label="资源 ID" width="120">
        <template #default="{ row }">{{ row.resource_id?.slice(0, 8) ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="变更" min-width="240">
        <template #default="{ row }">{{ fmtData(row.after_data ?? row.before_data) }}</template>
      </el-table-column>
      <el-table-column prop="trace_id" label="Trace" width="120">
        <template #default="{ row }">{{ row.trace_id?.slice(0, 8) ?? '-' }}</template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && logs.length === 0" description="暂无审计记录" />
  </el-card>
</template>
