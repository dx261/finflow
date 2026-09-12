<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { Account, Bank } from '@/types'

const router = useRouter()
const accounts = ref<Account[]>([])
const banks = ref<Bank[]>([])
const loading = ref(true)
const dialogVisible = ref(false)
const saving = ref(false)

const form = ref({
  bank_id: '',
  name: '',
  masked_account_no: '',
  account_type: 'CHECKING',
  currency: 'CNY',
  actual_balance: '0',
  minimum_balance: '0',
  include_in_allocation: true,
})

const accountTypeLabel: Record<string, string> = {
  CHECKING: '活期',
  SAVINGS: '储蓄',
  CREDIT_CARD: '信用卡',
  CASH: '现金',
  E_WALLET: '电子钱包',
  OTHER: '其他',
}

const statusTag: Record<string, string> = { ACTIVE: 'success', FROZEN: 'warning', CLOSED: 'info' }

onMounted(async () => {
  try {
    const [accRes, bankRes] = await Promise.all([
      api.get<Account[]>('/accounts'),
      api.get<Bank[]>('/banks'),
    ])
    accounts.value = accRes.data
    banks.value = bankRes.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
})

function openCreate(): void {
  form.value = {
    bank_id: banks.value[0]?.id ?? '',
    name: '',
    masked_account_no: '',
    account_type: 'CHECKING',
    currency: 'CNY',
    actual_balance: '0',
    minimum_balance: '0',
    include_in_allocation: true,
  }
  dialogVisible.value = true
}

async function createAccount(): Promise<void> {
  saving.value = true
  try {
    await api.post('/accounts', form.value)
    ElMessage.success('账户已创建')
    dialogVisible.value = false
    const res = await api.get<Account[]>('/accounts')
    accounts.value = res.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

function bankName(bankId: string): string {
  return banks.value.find((b) => b.id === bankId)?.name ?? bankId
}
</script>

<template>
  <div v-loading="loading">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>我的账户</span>
          <el-button type="primary" @click="openCreate">新建账户</el-button>
        </div>
      </template>

      <el-table :data="accounts" @row-click="(row: Account) => router.push(`/accounts/${row.id}`)">
        <el-table-column label="银行" width="140">
          <template #default="{ row }">{{ bankName(row.bank_id) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="账户名" width="160" />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">{{ accountTypeLabel[row.account_type] }}</template>
        </el-table-column>
        <el-table-column label="实际余额" width="140" align="right">
          <template #default="{ row }">¥{{ row.actual_balance }}</template>
        </el-table-column>
        <el-table-column label="虚拟预占" width="140" align="right">
          <template #default="{ row }">
            <span class="reserved">¥{{ row.reserved_amount }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最低保留" width="140" align="right">
          <template #default="{ row }">¥{{ row.minimum_balance }}</template>
        </el-table-column>
        <el-table-column label="可规划资金" width="140" align="right">
          <template #default="{ row }">
            <span class="available">¥{{ row.planning_available }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="(statusTag[row.status] ?? 'info') as any" size="small">{{
              row.status
            }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="accounts.length === 0" description="暂无账户，点击右上角新建" />
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建账户" width="480px">
      <el-form label-width="100px">
        <el-form-item label="银行" required>
          <el-select v-model="form.bank_id" style="width: 100%">
            <el-option v-for="b in banks" :key="b.id" :label="b.name" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="账户名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="尾号">
          <el-input v-model="form.masked_account_no" placeholder="如 ****1234" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.account_type" style="width: 100%">
            <el-option
              v-for="(label, key) in accountTypeLabel"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="实际余额">
          <el-input-number
            v-model="form.actual_balance"
            :precision="2"
            :step="1000"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="最低保留">
          <el-input-number
            v-model="form.minimum_balance"
            :precision="2"
            :step="1000"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="参与分配">
          <el-switch v-model="form.include_in_allocation" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createAccount">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.reserved {
  color: #e6a23c;
}
.available {
  color: #67c23a;
  font-weight: 600;
}
</style>
