<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { PaymentPlan, Reconciliation } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const isOwner = computed(() => auth.user?.role === 'OWNER')
const pending = ref<Reconciliation[]>([])
const payments = ref<Record<string, PaymentPlan>>({})
interface CandidateTransaction {
  id: string
  account_id: string
  transaction_date: string | null
  amount: string
  currency: string
  counterparty_name: string | null
  description: string
  external_reference: string | null
}
const transactions = ref<Record<string, CandidateTransaction>>({})
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
    const transactionEntries = await Promise.all(
      pending.value.map(async (recon) => {
        const response = await api.get<CandidateTransaction>(`/transactions/${recon.transaction_id}`)
        return [recon.transaction_id, response.data] as const
      }),
    )
    transactions.value = Object.fromEntries(transactionEntries)
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

function candidate(recon: Reconciliation): CandidateTransaction | undefined {
  return transactions.value[recon.transaction_id]
}

function scoreTitle(recon: Reconciliation): string {
  return [
    `金额 ${Math.round(recon.amount_score * 100)}%`,
    `账户 ${Math.round(recon.account_score * 100)}%`,
    `日期 ${Math.round(recon.date_score * 100)}%`,
    `对方 ${Math.round(recon.counterparty_score * 100)}%`,
    `流水号 ${Math.round(recon.reference_score * 100)}%`,
  ].join(' · ')
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
          <el-tooltip :content="scoreTitle(row)" placement="top">
            <el-progress
              :percentage="Math.round(row.total_score * 100)"
              :status="scoreColor(row.total_score) as any"
            />
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="金额" width="110" align="right">
        <template #default="{ row }">
          {{ paymentAmount(row) }}
        </template>
      </el-table-column>
      <el-table-column label="候选流水" min-width="240">
        <template #default="{ row }">
          <template v-if="candidate(row)">
            <div>{{ candidate(row)?.transaction_date ?? '日期未知' }} · {{ candidate(row)?.counterparty_name ?? '对方未知' }}</div>
            <div class="candidate-sub">{{ candidate(row)?.description || '无摘要' }}</div>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="流水金额" width="130" align="right">
        <template #default="{ row }">
          {{ candidate(row)?.currency }} {{ candidate(row)?.amount ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-tag :type="(statusTag[row.status] ?? 'info') as any" size="small">{{
            row.status === 'AUTO_MATCHED' ? '高置信度匹配' : '需要人工复核'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="isOwner" label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="act(row, 'confirm')">确认</el-button>
          <el-button size="small" type="danger" @click="act(row, 'reject')">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && pending.length === 0" description="没有待审核的匹配，一切正常" />
  </el-card>
</template>

<style scoped>
.candidate-sub {
  margin-top: 3px;
  color: #909399;
  font-size: 12px;
}
</style>
