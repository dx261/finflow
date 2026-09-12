<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { PaymentPlan, Reconciliation } from '@/types'

const pending = ref<Reconciliation[]>([])
const payments = ref<Record<string, PaymentPlan>>({})
const loading = ref(true)

const statusTag: Record<string, string> = {
  AUTO_MATCHED: 'success',
  REVIEW_REQUIRED: 'warning',
  CONFIRMED: 'success',
  REJECTED: 'danger',
}

onMounted(async () => {
  try {
    const [recRes, payRes] = await Promise.all([
      api.get<Reconciliation[]>('/reconciliations/pending'),
      api.get<PaymentPlan[]>('/payments'),
    ])
    pending.value = recRes.data
    payments.value = Object.fromEntries(payRes.data.map((p) => [p.id, p]))
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
})

async function act(recon: Reconciliation, action: 'confirm' | 'reject'): Promise<void> {
  try {
    await api.post(`/reconciliations/${recon.id}/${action}`)
    ElMessage.success(action === 'confirm' ? '已确认并结算' : '已拒绝')
    pending.value = pending.value.filter((r) => r.id !== recon.id)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function paymentName(recon: Reconciliation): string {
  return payments.value[recon.payment_id]?.name ?? recon.payment_id.slice(0, 8)
}

function paymentAmount(recon: Reconciliation): string {
  return payments.value[recon.payment_id]?.amount ?? '-'
}

function scoreColor(score: number): string {
  return score >= 0.8 ? 'success' : score >= 0.6 ? 'warning' : 'danger'
}
</script>

<template>
  <el-card>
    <template #header>对账工作台 — 待审核匹配</template>
    <el-table v-loading="loading" :data="pending">
      <el-table-column label="付款" min-width="140">
        <template #default="{ row }">{{ paymentName(row) }}</template>
      </el-table-column>
      <el-table-column label="匹配分数" width="160">
        <template #default="{ row }">
          <el-progress
            :percentage="Math.round(row.total_score * 100)"
            :status="scoreColor(row.total_score) as any"
          />
        </template>
      </el-table-column>
      <el-table-column label="金额" width="110" align="right">
        <template #default="{ row }">
          {{ paymentAmount(row) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-tag :type="(statusTag[row.status] ?? 'info') as any" size="small">{{
            row.status
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="act(row, 'confirm')">确认</el-button>
          <el-button size="small" type="danger" @click="act(row, 'reject')">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && pending.length === 0" description="没有待审核的匹配，一切正常" />
  </el-card>
</template>
