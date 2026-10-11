<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { Account, StatementImport, StatementImportDetail } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const isOwner = computed(() => auth.user?.role === 'OWNER')
const accounts = ref<Account[]>([])
const accountFilter = ref('')
const forceImport = ref(false)
const fileList = ref<UploadFile[]>([])
const importing = ref(false)

const imports = ref<StatementImport[]>([])
const loading = ref(false)

const detailVisible = ref(false)
const detail = ref<StatementImportDetail | null>(null)
const detailLoading = ref(false)

let pollTimer: ReturnType<typeof setTimeout> | null = null

const statusTag: Record<string, string> = {
  UPLOADED: 'info',
  QUEUED: 'info',
  PARSING: 'warning',
  PARTIAL_SUCCESS: 'warning',
  SUCCESS: 'success',
  FAILED: 'danger',
}

const statusText: Record<string, string> = {
  UPLOADED: '已上传',
  QUEUED: '排队中',
  PARSING: '解析中',
  PARTIAL_SUCCESS: '部分成功',
  SUCCESS: '成功',
  FAILED: '失败',
}

function hasPending(records: StatementImport[]): boolean {
  return records.some((r) => r.status === 'UPLOADED' || r.status === 'QUEUED' || r.status === 'PARSING')
}

async function loadImports(): Promise<void> {
  if (!accountFilter.value) return
  loading.value = true
  try {
    const res = await api.get<StatementImport[]>('/statements', {
      params: { account_id: accountFilter.value },
    })
    imports.value = res.data
    schedulePoll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function schedulePoll(): void {
  if (pollTimer) clearTimeout(pollTimer)
  if (hasPending(imports.value)) {
    pollTimer = setTimeout(() => void loadImports(), 3000)
  }
}

function onAccountChange(): void {
  void loadImports()
}

async function uploadFiles(): Promise<void> {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择账单文件')
    return
  }
  if (!accountFilter.value) {
    ElMessage.warning('请先选择目标账户')
    return
  }
  importing.value = true
  try {
    for (const file of fileList.value) {
      const raw = file.raw
      if (!raw) continue
      const form = new FormData()
      form.append('account_id', accountFilter.value)
      form.append('file', raw)
      const res = await api.post('/statements/upload', form, {
        params: { force_import: forceImport.value },
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const body = res.data as { is_duplicate: boolean; message: string }
      if (body.is_duplicate) {
        ElMessage.warning(`「${raw.name}」${body.message}`)
      } else {
        ElMessage.success(`「${raw.name}」已提交，等待解析`)
      }
    }
    fileList.value = []
    await loadImports()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    importing.value = false
  }
}

async function showDetail(row: StatementImport): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const res = await api.get<StatementImportDetail>(`/statements/${row.id}`)
    detail.value = res.data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

function dateLabel(d: string | null): string {
  return d ? d.slice(0, 10) : '-'
}

function createdAt(d: string): string {
  return d.replace('T', ' ').slice(0, 19)
}

onMounted(async () => {
  try {
    const res = await api.get<Account[]>('/accounts')
    accounts.value = res.data
    accountFilter.value = accounts.value[0]?.id ?? ''
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
  await loadImports()
})

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<template>
  <el-card>
    <template #header>账单导入</template>

    <el-form inline class="filter-bar">
      <el-form-item label="目标账户">
        <el-select
          v-model="accountFilter"
          placeholder="选择账户"
          style="width: 220px"
          @change="onAccountChange"
        >
          <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="isOwner">
        <el-switch v-model="forceImport" active-text="重新处理同一文件（流水仍会去重）" />
      </el-form-item>
    </el-form>

    <el-upload
      v-if="isOwner"
      v-model:file-list="fileList"
      drag
      multiple
      :auto-upload="false"
      accept=".xlsx,.xls,.csv"
      class="upload-zone"
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">
        拖拽账单文件到此处，或 <em>点击选择</em>（支持 xlsx / csv）
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持 ICBC / 招商银行 / 通用 CSV 格式。文件将先校验重复，再异步解析入库。
        </div>
      </template>
    </el-upload>

    <el-button
      v-if="isOwner"
      type="primary"
      class="upload-btn"
      :loading="importing"
      :disabled="fileList.length === 0 || !accountFilter"
      @click="uploadFiles"
    >
      开始导入（{{ fileList.length }}）
    </el-button>

    <el-divider />

    <h4 class="section-title">导入记录</h4>
    <el-table v-loading="loading" :data="imports" size="small" @row-click="showDetail">
      <el-table-column prop="original_filename" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="(statusTag[row.status] ?? 'info') as any" size="small">
            {{ statusText[row.status] ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="区间" width="200">
        <template #default="{ row }">
          {{ dateLabel(row.statement_start_date) }} ~ {{ dateLabel(row.statement_end_date) }}
        </template>
      </el-table-column>
      <el-table-column prop="total_rows" label="总行数" width="80" align="right" />
      <el-table-column prop="success_rows" label="成功" width="80" align="right" />
      <el-table-column prop="failed_rows" label="失败" width="80" align="right" />
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ createdAt(row.created_at) }}</template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && imports.length === 0" description="该账户还没有导入记录" />

    <el-dialog v-model="detailVisible" title="导入详情" width="720px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="文件" :span="2">{{
              detail.import_record.original_filename
            }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="(statusTag[detail.import_record.status] ?? 'info') as any" size="small">
                {{ statusText[detail.import_record.status] ?? detail.import_record.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="解析结果">
              {{ detail.import_record.success_rows }} 成功 / {{ detail.import_record.failed_rows }} 失败
            </el-descriptions-item>
          </el-descriptions>

          <h4 class="section-title">错误明细</h4>
          <el-table v-if="detail.errors.length > 0" :data="detail.errors" size="small" max-height="320">
            <el-table-column prop="row_number" label="行号" width="70" align="right">
              <template #default="{ row }">{{ row.row_number ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="field" label="字段" width="110">
              <template #default="{ row }">{{ row.field ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="error_code" label="错误码" width="150" />
            <el-table-column prop="message" label="说明" min-width="220" show-overflow-tooltip />
          </el-table>
          <el-empty v-else description="没有解析错误" :image-size="60" />
        </template>
      </div>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.filter-bar {
  margin-bottom: 4px;
}
.upload-zone {
  margin-bottom: 12px;
}
.upload-btn {
  margin-bottom: 8px;
}
.section-title {
  margin: 4px 0 12px;
  font-weight: 600;
}
</style>
