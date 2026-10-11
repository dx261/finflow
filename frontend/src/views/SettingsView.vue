<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { api, errorMessage } from '@/api/client'
import type { Bank } from '@/types'

const auth = useAuthStore()
const isOwner = computed(() => auth.user?.role === 'OWNER')
const profile = computed(() => auth.user)

const banks = ref<Bank[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const form = ref({
  code: '',
  name: '',
  country: 'CN',
  statement_parser_type: 'GENERIC',
})

const parserLabel: Record<string, string> = {
  ICBC: '工商银行专属解析',
  CMB: '招商银行专属解析',
  GENERIC: '通用解析',
}

async function loadBanks(): Promise<void> {
  loading.value = true
  try {
    const res = await api.get<Bank[]>('/banks')
    banks.value = res.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  form.value = {
    code: '',
    name: '',
    country: 'CN',
    statement_parser_type: 'GENERIC',
  }
  dialogVisible.value = true
}

async function createBank(): Promise<void> {
  saving.value = true
  try {
    await api.post('/banks', {
      code: form.value.code.toUpperCase(),
      name: form.value.name,
      country: form.value.country,
      statement_parser_type: form.value.statement_parser_type,
    })
    ElMessage.success('银行已添加')
    dialogVisible.value = false
    await loadBanks()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function removeBank(bank: Bank): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除银行「${bank.name}」？已有账户引用的银行无法删除。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await api.delete(`/banks/${bank.id}`)
    ElMessage.success('银行已删除')
    await loadBanks()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(loadBanks)
</script>

<template>
  <div class="settings-page">
    <el-card v-if="!auth.demoMode">
      <template #header>账户资料</template>

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
    </el-card>

    <el-card class="bank-card">
      <template #header>
        <div class="card-header">
          <span>银行目录</span>
          <el-button v-if="isOwner" type="primary" size="small" @click="openCreate">
            添加银行
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="banks" size="small">
        <el-table-column label="代码" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="解析器" width="180">
          <template #default="{ row }">
            {{ parserLabel[row.statement_parser_type] ?? row.statement_parser_type }}
          </template>
        </el-table-column>
        <el-table-column prop="country" label="国家" width="80" />
        <el-table-column v-if="isOwner" label="操作" width="90">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="removeBank(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-alert v-if="!isOwner" type="info" :closable="false" class="owner-hint">
        只有 OWNER 可以管理银行目录。
      </el-alert>
    </el-card>

    <el-card>
      <el-alert type="info" :closable="false">
        <p>
          <b>FinFlow 安全边界</b
          >：系统只做资金规划、分配建议、对账确认，绝不直接操作真实银行账户。所有真实资金操作均由你在银行端人工完成。
        </p>
        <p>金额一律以 Decimal 精确处理，不使用浮点数。</p>
      </el-alert>
    </el-card>

    <el-dialog v-model="dialogVisible" title="添加银行" width="440px">
      <el-form label-width="90px">
        <el-form-item label="银行代码" required>
          <el-input v-model="form.code" placeholder="如 ICBC / CMB / CCB" maxlength="20" />
        </el-form-item>
        <el-form-item label="银行名称" required>
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <el-form-item label="国家">
          <el-input v-model="form.country" maxlength="2" />
        </el-form-item>
        <el-form-item label="账单解析器">
          <el-select v-model="form.statement_parser_type" style="width: 100%">
            <el-option
              v-for="(label, value) in parserLabel"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createBank">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.owner-hint {
  margin-top: 12px;
}
</style>
