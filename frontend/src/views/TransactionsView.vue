<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { Account } from '@/types'

interface Txn {
  id: string
  account_id: string
  transaction_date: string | null
  direction: 'DEBIT' | 'CREDIT'
  amount: string
  currency: string
  counterparty_name: string | null
  description: string
  transaction_type: string
  external_reference: string | null
}

const transactions = ref<Txn[]>([])
const accounts = ref<Account[]>([])
const loading = ref(true)

const filters = ref({
  account_id: '' as string,
  date_from: '' as string,
  date_to: '' as string,
  keyword: '',
  direction: '' as string,
})

const typeTag: Record<string, string> = {
  NORMAL: 'info',
  REFUND: 'success',
  REVERSAL: 'danger',
  TRANSFER: 'warning',
  FEE: 'primary',
  INTEREST: 'success',
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filters.value.account_id) params.account_id = filters.value.account_id
    if (filters.value.date_from) params.date_from = filters.value.date_from
    if (filters.value.date_to) params.date_to = filters.value.date_to
    if (filters.value.keyword) params.keyword = filters.value.keyword
    if (filters.value.direction) params.direction = filters.value.direction
    const res = await api.get<Txn[]>('/transactions', { params })
    transactions.value = res.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const res = await api.get<Account[]>('/accounts')
    accounts.value = res.data
  } catch {
    // accounts load failure is non-fatal
  }
  await load()
})

function accountName(id: string): string {
  return accounts.value.find((a) => a.id === id)?.name ?? id.slice(0, 8)
}
</script>

<template>
  <el-card>
    <template #header>交易流水</template>

    <el-form inline class="filter-bar">
      <el-form-item label="账户">
        <el-select
          v-model="filters.account_id"
          clearable
          placeholder="全部"
          style="width: 160px"
          @change="load"
        >
          <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker
          v-model="filters.date_from"
          type="date"
          placeholder="开始"
          value-format="YYYY-MM-DD"
          style="width: 140px"
        />
        <span class="sep">-</span>
        <el-date-picker
          v-model="filters.date_to"
          type="date"
          placeholder="结束"
          value-format="YYYY-MM-DD"
          style="width: 140px"
        />
      </el-form-item>
      <el-form-item label="方向">
        <el-select v-model="filters.direction" clearable placeholder="全部" style="width: 110px">
          <el-option label="支出" value="DEBIT" />
          <el-option label="收入" value="CREDIT" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          placeholder="摘要/对方"
          clearable
          style="width: 160px"
          @keyup.enter="load"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="transactions" size="small">
      <el-table-column prop="transaction_date" label="日期" width="110" />
      <el-table-column label="账户" width="120">
        <template #default="{ row }">{{ accountName(row.account_id) }}</template>
      </el-table-column>
      <el-table-column prop="description" label="摘要" min-width="180" />
      <el-table-column prop="counterparty_name" label="对方" min-width="120">
        <template #default="{ row }">{{ row.counterparty_name ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="金额" width="140" align="right">
        <template #default="{ row }">
          <span :class="row.direction === 'DEBIT' ? 'debit' : 'credit'">
            {{ row.direction === 'DEBIT' ? '-' : '+' }}{{ row.amount }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="(typeTag[row.transaction_type] ?? 'info') as any" size="small">{{
            row.transaction_type
          }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && transactions.length === 0" description="没有匹配的交易" />
  </el-card>
</template>

<style scoped>
.filter-bar {
  margin-bottom: 8px;
}
.sep {
  margin: 0 6px;
  color: #909399;
}
.debit {
  color: #f56c6c;
}
.credit {
  color: #67c23a;
}
</style>
