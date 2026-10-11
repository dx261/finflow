<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { Account, CashFlowPlan, RecurringPayment } from '@/types'

const auth = useAuthStore()
const isOwner = computed(() => auth.user?.role === 'OWNER')
const accounts = ref<Account[]>([])
const recurring = ref<RecurringPayment[]>([])
const cashflows = ref<CashFlowPlan[]>([])
const loading = ref(true)
const saving = ref(false)
const recurringVisible = ref(false)
const cashflowVisible = ref(false)

const recurringForm = ref({
  name: '',
  amount: 0,
  currency: 'CNY',
  frequency: 'MONTHLY',
  day_of_month: 1,
  start_date: '',
  end_date: '',
  preferred_account_id: '',
  priority: 'NORMAL',
})

const cashflowForm = ref({
  type: 'INCOME',
  name: '',
  amount: 0,
  currency: 'CNY',
  date: '',
  account_id: '',
})

const frequencyLabel: Record<string, string> = {
  WEEKLY: '每周',
  MONTHLY: '每月',
  QUARTERLY: '每季度',
  YEARLY: '每年',
}

function accountName(id: string | null): string {
  if (!id) return '待指定账户'
  return accounts.value.find((account) => account.id === id)?.name ?? id.slice(0, 8)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [accountResponse, recurringResponse, cashflowResponse] = await Promise.all([
      api.get<Account[]>('/accounts'),
      api.get<RecurringPayment[]>('/recurring'),
      api.get<CashFlowPlan[]>('/cashflow-plans'),
    ])
    accounts.value = accountResponse.data
    recurring.value = recurringResponse.data
    cashflows.value = cashflowResponse.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function openRecurring(): void {
  recurringForm.value = {
    name: '',
    amount: 0,
    currency: 'CNY',
    frequency: 'MONTHLY',
    day_of_month: 1,
    start_date: new Date().toISOString().slice(0, 10),
    end_date: '',
    preferred_account_id: '',
    priority: 'NORMAL',
  }
  recurringVisible.value = true
}

function openCashflow(): void {
  cashflowForm.value = {
    type: 'INCOME',
    name: '',
    amount: 0,
    currency: 'CNY',
    date: new Date().toISOString().slice(0, 10),
    account_id: '',
  }
  cashflowVisible.value = true
}

function syncRecurringCurrency(accountId: string): void {
  const account = accounts.value.find((item) => item.id === accountId)
  if (account) recurringForm.value.currency = account.currency
}

function syncCashflowCurrency(accountId: string): void {
  const account = accounts.value.find((item) => item.id === accountId)
  if (account) cashflowForm.value.currency = account.currency
}

async function createRecurring(): Promise<void> {
  saving.value = true
  try {
    await api.post('/recurring', {
      ...recurringForm.value,
      end_date: recurringForm.value.end_date || null,
      preferred_account_id: recurringForm.value.preferred_account_id || null,
    })
    ElMessage.success('周期付款规则已创建')
    recurringVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function createCashflow(): Promise<void> {
  saving.value = true
  try {
    await api.post('/cashflow-plans', {
      ...cashflowForm.value,
      account_id: cashflowForm.value.account_id || null,
    })
    ElMessage.success('现金流计划已创建')
    cashflowVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function toggleRecurring(item: RecurringPayment): Promise<void> {
  try {
    await api.put(`/recurring/${item.id}`, { enabled: !item.enabled })
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function cancelCashflow(item: CashFlowPlan): Promise<void> {
  try {
    await api.put(`/cashflow-plans/${item.id}`, { status: 'CANCELLED' })
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function remove(kind: 'recurring' | 'cashflow-plans', id: string): Promise<void> {
  try {
    await ElMessageBox.confirm('删除后无法恢复，是否继续？', '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await api.delete(`/${kind}/${id}`)
    ElMessage.success('已删除')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="planning-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <div class="title">周期付款</div>
            <div class="subtitle">按周期自动生成付款计划，不会自动操作真实资金。</div>
          </div>
          <el-button v-if="isOwner" type="primary" @click="openRecurring">新增规则</el-button>
        </div>
      </template>
      <el-table :data="recurring" size="small">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="金额" width="150" align="right">
          <template #default="{ row }">{{ row.currency }} {{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="周期" width="100">
          <template #default="{ row }">{{ frequencyLabel[row.frequency] }}</template>
        </el-table-column>
        <el-table-column prop="day_of_month" label="执行日" width="90" />
        <el-table-column label="首选账户" min-width="140">
          <template #default="{ row }">{{ accountName(row.preferred_account_id) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="isOwner" label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="toggleRecurring(row)">{{ row.enabled ? '停用' : '启用' }}</el-button>
            <el-button link type="danger" @click="remove('recurring', row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="recurring.length === 0" description="暂无周期付款规则" />
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <div class="title">未来现金流</div>
            <div class="subtitle">录入工资、奖金、保险等非付款计划现金流。</div>
          </div>
          <el-button v-if="isOwner" type="primary" @click="openCashflow">新增现金流</el-button>
        </div>
      </template>
      <el-table :data="cashflows" size="small">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.type === 'INCOME' ? 'success' : 'warning'">{{ row.type === 'INCOME' ? '收入' : '支出' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="150" align="right">
          <template #default="{ row }">{{ row.currency }} {{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="账户" min-width="140">
          <template #default="{ row }">{{ accountName(row.account_id) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column v-if="isOwner" label="操作" width="150">
          <template #default="{ row }">
            <el-button v-if="row.status === 'ACTIVE'" link type="warning" @click="cancelCashflow(row)">取消</el-button>
            <el-button link type="danger" @click="remove('cashflow-plans', row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="cashflows.length === 0" description="暂无未来现金流" />
    </el-card>

    <el-dialog v-model="recurringVisible" title="新增周期付款" width="520px">
      <el-form label-width="100px">
        <el-form-item label="名称" required><el-input v-model="recurringForm.name" /></el-form-item>
        <el-form-item label="金额" required><el-input-number v-model="recurringForm.amount" :min="0.01" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="周期"><el-select v-model="recurringForm.frequency" style="width: 100%"><el-option v-for="(label, value) in frequencyLabel" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="执行日"><el-input-number v-model="recurringForm.day_of_month" :min="1" :max="31" /></el-form-item>
        <el-form-item label="开始日期" required><el-date-picker v-model="recurringForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="recurringForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="首选账户"><el-select v-model="recurringForm.preferred_account_id" clearable style="width: 100%" @change="syncRecurringCurrency"><el-option v-for="account in accounts" :key="account.id" :label="`${account.name} · ${account.currency}`" :value="account.id" /></el-select></el-form-item>
        <el-form-item label="币种"><el-input v-model="recurringForm.currency" maxlength="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="recurringVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="createRecurring">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="cashflowVisible" title="新增未来现金流" width="500px">
      <el-form label-width="100px">
        <el-form-item label="类型"><el-radio-group v-model="cashflowForm.type"><el-radio-button value="INCOME">收入</el-radio-button><el-radio-button value="EXPENSE">支出</el-radio-button></el-radio-group></el-form-item>
        <el-form-item label="名称" required><el-input v-model="cashflowForm.name" /></el-form-item>
        <el-form-item label="金额" required><el-input-number v-model="cashflowForm.amount" :min="0.01" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="日期" required><el-date-picker v-model="cashflowForm.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="账户"><el-select v-model="cashflowForm.account_id" clearable style="width: 100%" @change="syncCashflowCurrency"><el-option v-for="account in accounts" :key="account.id" :label="`${account.name} · ${account.currency}`" :value="account.id" /></el-select></el-form-item>
        <el-form-item label="币种"><el-input v-model="cashflowForm.currency" maxlength="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="cashflowVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="createCashflow">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.planning-page { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.title { font-weight: 600; }
.subtitle { margin-top: 4px; color: #909399; font-size: 12px; }
</style>
