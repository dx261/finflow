<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { Account, Allocation, PaymentPlan } from '@/types'

const route = useRoute()
const accountId = String(route.params.id)

const account = ref<Account | null>(null)
const allocations = ref<Allocation[]>([])
const payments = ref<PaymentPlan[]>([])
const loading = ref(true)

const typeLabel: Record<string, string> = {
  CHECKING: '活期',
  SAVINGS: '储蓄',
  CREDIT_CARD: '信用卡',
  CASH: '现金',
  E_WALLET: '电子钱包',
  OTHER: '其他',
}

onMounted(async () => {
  try {
    const [accRes, payRes] = await Promise.all([
      api.get<Account>(`/accounts/${accountId}`),
      api.get<PaymentPlan[]>('/payments'),
    ])
    account.value = accRes.data
    payments.value = payRes.data

    const allocRes = await Promise.all(
      payments.value.map((p) =>
        api
          .get<Allocation[]>(`/payments/${p.id}/allocations`)
          .then((r) => r.data.filter((a) => a.account_id === accountId))
          .catch(() => [] as Allocation[]),
      ),
    )
    allocations.value = allocRes.flat()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading">
    <el-card v-if="account">
      <template #header>
        <div class="card-header">
          <span>{{ account.name }}</span>
          <el-tag type="success" size="small">{{ account.status }}</el-tag>
        </div>
      </template>

      <el-descriptions :column="3" border>
        <el-descriptions-item label="类型">{{
          typeLabel[account.account_type] ?? account.account_type
        }}</el-descriptions-item>
        <el-descriptions-item label="币种">{{ account.currency }}</el-descriptions-item>
        <el-descriptions-item label="账户尾号">{{
          account.masked_account_no ?? '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="实际余额">
          <span class="strong">¥{{ account.actual_balance }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="虚拟预占">
          <span class="reserved">¥{{ account.reserved_amount }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="最低保留">¥{{ account.minimum_balance }}</el-descriptions-item>
        <el-descriptions-item label="可规划资金" :span="3">
          <span class="available">¥{{ account.planning_available }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="allocations.length" class="mt-16">
      <template #header>预占分配</template>
      <el-table :data="allocations" size="small">
        <el-table-column label="付款" min-width="160">
          <template #default="{ row }">
            {{ payments.find((p) => p.id === row.payment_id)?.name ?? row.payment_id.slice(0, 8) }}
          </template>
        </el-table-column>
        <el-table-column label="分配金额" width="140" align="right">
          <template #default="{ row }">¥{{ row.allocated_amount }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.strong {
  font-weight: 700;
}
.reserved {
  color: #e6a23c;
}
.available {
  color: #67c23a;
  font-weight: 600;
}
.mt-16 {
  margin-top: 16px;
}
</style>
