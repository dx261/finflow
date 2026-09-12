<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { Account, Allocation, PaymentPlan } from '@/types'

const payments = ref<PaymentPlan[]>([])
const accounts = ref<Account[]>([])
const loading = ref(true)
const dialogVisible = ref(false)
const saving = ref(false)

const statusFilter = ref('')
const form = ref({
  name: '',
  amount: '0',
  planned_date: '',
  priority: 'NORMAL',
  preferred_account_id: '',
})

const statusTag: Record<string, string> = {
  DRAFT: 'info',
  PLANNED: 'primary',
  ALLOCATED: 'warning',
  RESERVED: 'warning',
  WAITING_MANUAL_EXECUTION: 'danger',
  MANUALLY_EXECUTED: 'info',
  RECONCILING: 'warning',
  SETTLED: 'success',
  EXCEPTION: 'danger',
  CANCELLED: 'info',
}

const priorityLabel: Record<string, string> = {
  LOW: '低',
  NORMAL: '普通',
  HIGH: '高',
  URGENT: '紧急',
}

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = statusFilter.value ? { status: statusFilter.value } : {}
    const [payRes, accRes] = await Promise.all([
      api.get<PaymentPlan[]>('/payments', { params }),
      api.get<Account[]>('/accounts'),
    ])
    payments.value = payRes.data
    accounts.value = accRes.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  form.value = {
    name: '',
    amount: '0',
    planned_date: '',
    priority: 'NORMAL',
    preferred_account_id: '',
  }
  dialogVisible.value = true
}

async function createPayment(): Promise<void> {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      name: form.value.name,
      amount: form.value.amount,
      planned_date: form.value.planned_date,
      priority: form.value.priority,
    }
    if (form.value.preferred_account_id)
      payload.preferred_account_id = form.value.preferred_account_id
    await api.post('/payments', payload)
    ElMessage.success('付款计划已创建')
    dialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function transition(payment: PaymentPlan, target: string): Promise<void> {
  try {
    await api.post(`/payments/${payment.id}/transition`, { target_status: target })
    ElMessage.success(`已变为 ${target}`)
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function manualExecute(payment: PaymentPlan): Promise<void> {
  try {
    const payload: Record<string, unknown> = {}
    if (payment.preferred_account_id) payload.account_id = payment.preferred_account_id
    await api.post(`/payments/${payment.id}/manual-execution`, payload)
    ElMessage.success('已标记人工执行完成')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function viewAllocations(payment: PaymentPlan): Promise<void> {
  try {
    const res = await api.get<Allocation[]>(`/payments/${payment.id}/allocations`)
    const lines = res.data
      .map((a) => {
        const name = accounts.value.find((acc) => acc.id === a.account_id)?.name ?? a.account_id
        return `${name}: ¥${a.allocated_amount} (${a.status})`
      })
      .join('\n')
    await ElMessageBox.alert(lines || '暂无分配', `${payment.name} 的资金分配`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>付款计划</span>
        <div>
          <el-select
            v-model="statusFilter"
            clearable
            placeholder="全部状态"
            style="width: 200px; margin-right: 12px"
            @change="load"
          >
            <el-option v-for="key in Object.keys(statusTag)" :key="key" :label="key" :value="key" />
          </el-select>
          <el-button type="primary" @click="openCreate">新建付款计划</el-button>
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="payments">
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column label="金额" width="130" align="right">
        <template #default="{ row }">¥{{ row.amount }}</template>
      </el-table-column>
      <el-table-column prop="planned_date" label="计划日期" width="110" />
      <el-table-column label="优先级" width="90">
        <template #default="{ row }">{{ priorityLabel[row.priority] }}</template>
      </el-table-column>
      <el-table-column label="状态" width="180">
        <template #default="{ row }">
          <el-tag :type="(statusTag[row.status] ?? 'info') as any" size="small">{{
            row.status
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="330">
        <template #default="{ row }">
          <el-button size="small" @click="viewAllocations(row)">分配</el-button>
          <template v-if="row.status === 'DRAFT'">
            <el-button size="small" type="primary" @click="transition(row, 'PLANNED')"
              >计划</el-button
            >
          </template>
          <template v-else-if="row.status === 'PLANNED'">
            <el-button size="small" type="primary" @click="transition(row, 'ALLOCATED')"
              >分配</el-button
            >
          </template>
          <template v-else-if="row.status === 'RESERVED'">
            <el-button
              size="small"
              type="warning"
              @click="transition(row, 'WAITING_MANUAL_EXECUTION')"
              >待执行</el-button
            >
          </template>
          <template v-else-if="row.status === 'WAITING_MANUAL_EXECUTION'">
            <el-button size="small" type="success" @click="manualExecute(row)"
              >已人工执行</el-button
            >
          </template>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && payments.length === 0" description="暂无付款计划" />

    <el-dialog v-model="dialogVisible" title="新建付款计划" width="460px">
      <el-form label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="金额" required>
          <el-input-number v-model="form.amount" :precision="2" :min="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="计划日期" required>
          <el-date-picker
            v-model="form.planned_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option
              v-for="(label, key) in priorityLabel"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="首选账户">
          <el-select v-model="form.preferred_account_id" clearable style="width: 100%">
            <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createPayment">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
