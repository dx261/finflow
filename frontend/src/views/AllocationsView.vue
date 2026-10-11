<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { api, errorMessage } from '@/api/client'
import type { Account, Allocation, PaymentPlan } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const isOwner = computed(() => auth.user?.role === 'OWNER')
const payments = ref<PaymentPlan[]>([])
const accounts = ref<Account[]>([])
const allocations = ref<Allocation[]>([])
const selectedPaymentId = ref('')
const loading = ref(false)
const acting = ref(false)

const statusTag: Record<string, string> = {
  PLANNED: 'primary',
  ALLOCATED: 'warning',
  RESERVED: 'danger',
}

const statusLabel: Record<string, string> = {
  PLANNED: '待分配',
  ALLOCATED: '已出方案',
  RESERVED: '已预留',
}

// Editable manual overrides per account (null = no allocation).
const edits = ref<Record<string, number | null>>({})

const selectedPayment = computed<PaymentPlan | null>(
  () => payments.value.find((p) => p.id === selectedPaymentId.value) ?? null,
)

const allocatable = computed(() => accounts.value.filter((a) => a.include_in_allocation))

const currentProposed = computed(() =>
  allocations.value.filter((a) => a.status === 'PROPOSED'),
)

const reservedMap = computed(() => {
  const map: Record<string, string> = {}
  for (const a of allocations.value) {
    if (a.status === 'RESERVED') map[a.account_id] = a.allocated_amount
  }
  return map
})

const totalAllocated = computed(() => {
  let total = 0
  for (const item of Object.entries(edits.value)) {
    total += item[1] ? item[1] : 0
  }
  return total
})

const totalMatches = computed(
  () => selectedPayment.value !== null && Math.abs(totalAllocated.value - Number(selectedPayment.value.amount)) < 0.005,
)

const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9254de', '#36cfc9']

function accountColor(index: number): string {
  return colors[index % colors.length]
}

function fmt(n: string | number | null | undefined): string {
  if (n === null || n === undefined) return '-'
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function accountName(id: string): string {
  return accounts.value.find((a) => a.id === id)?.name ?? id.slice(0, 8)
}

async function loadPayments(): Promise<void> {
  loading.value = true
  try {
    const res = await api.get<PaymentPlan[]>('/payments')
    payments.value = res.data.filter((p) => ['PLANNED', 'ALLOCATED', 'RESERVED'].includes(p.status))
    const requestedPayment = typeof route.query.payment === 'string' ? route.query.payment : ''
    if (requestedPayment && payments.value.some((p) => p.id === requestedPayment)) {
      selectedPaymentId.value = requestedPayment
    }
    if (selectedPaymentId.value && !payments.value.some((p) => p.id === selectedPaymentId.value)) {
      selectedPaymentId.value = payments.value[0]?.id ?? ''
    } else if (!selectedPaymentId.value) {
      selectedPaymentId.value = payments.value[0]?.id ?? ''
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadAllocations(): Promise<void> {
  if (!selectedPaymentId.value) return
  try {
    const res = await api.get<Allocation[]>(`/payments/${selectedPaymentId.value}/allocations`)
    allocations.value = res.data
    resetEdits()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function resetEdits(): void {
  const map: Record<string, number | null> = {}
  for (const acc of allocatable.value) {
    const proposed = currentProposed.value.find((a) => a.account_id === acc.id)
    if (proposed) {
      map[acc.id] = Number(proposed.allocated_amount)
    } else if (reservedMap.value[acc.id]) {
      // No editable proposal left (already reserved): show the reserved split
      // as a read-only visual so the funding bar stays informative.
      map[acc.id] = Number(reservedMap.value[acc.id])
    } else {
      map[acc.id] = null
    }
  }
  edits.value = map
}

async function generatePreview(): Promise<void> {
  if (!selectedPaymentId.value) return
  acting.value = true
  try {
    await api.post(`/payments/${selectedPaymentId.value}/allocations/preview`)
    ElMessage.success('建议方案已生成（尚未预留资金）')
    await Promise.all([loadPayments(), loadAllocations()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    acting.value = false
  }
}

async function applyOverride(): Promise<void> {
  if (!selectedPaymentId.value || !selectedPayment.value) return
  const items = Object.entries(edits.value)
    .filter(([, v]) => v !== null && v > 0)
    .map(([account_id, amount]) => ({ account_id, amount }))
  if (items.length === 0) {
    ElMessage.warning('请至少给一个账户填入金额')
    return
  }
  if (!totalMatches.value) {
    ElMessage.warning(`分配总额 ${fmt(totalAllocated.value)} 必须等于付款金额 ${fmt(selectedPayment.value.amount)}`)
    return
  }
  acting.value = true
  try {
    await api.put(`/payments/${selectedPaymentId.value}/allocations/override`, items)
    ElMessage.success('手动分配已应用')
    await loadAllocations()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    acting.value = false
  }
}

async function confirmReservation(): Promise<void> {
  if (!selectedPaymentId.value) return
  if (currentProposed.value.length === 0) {
    ElMessage.warning('还没有建议方案，请先生成或手动分配')
    return
  }
  acting.value = true
  try {
    await api.post(`/payments/${selectedPaymentId.value}/allocations/confirm`)
    ElMessage.success('资金已虚拟预留（未动真实资金）')
    await Promise.all([loadPayments(), loadAllocations()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    acting.value = false
  }
}

// Visualization geometry ------------------------------------------------

// Segments of the funding bar: account allocations + uncovered gap.
const segments = computed(() => {
  const amount = Number(selectedPayment.value?.amount ?? 0)
  const segs: Array<{ accountId: string | null; value: number; color: string }> = []
  let used = 0
  allocatable.value.forEach((acc, i) => {
    const value = Number(edits.value[acc.id] || 0)
    if (value > 0) {
      segs.push({ accountId: acc.id, value, color: accountColor(i) })
      used += value
    }
  })
  if (amount - used > 0.005) {
    segs.push({ accountId: null, value: amount - used, color: '#e0e3e8' })
  }
  return segs
})

function percent(value: number, capacity: string): number {
  const available = Number(capacity)
  if (available <= 0) return value > 0 ? 100 : 0
  return Math.max(0, Math.min(100, (value / available) * 100))
}

watch(selectedPaymentId, () => void loadAllocations())
onMounted(async () => {
  try {
    const accRes = await api.get<Account[]>('/accounts')
    accounts.value = accRes.data
    await loadPayments()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
})
</script>

<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>分配可视化 — 资金从哪里来</span>
        <div class="header-right">
          <el-select
            v-model="selectedPaymentId"
            placeholder="选择付款计划"
            style="width: 260px"
          >
            <el-option v-for="p in payments" :key="p.id" :value="p.id">
              <span>{{ p.name }}</span>
              <span class="opt-sub">¥{{ p.amount }} · {{ statusLabel[p.status] }}</span>
            </el-option>
          </el-select>
          <el-button
            v-if="isOwner"
            type="primary"
            :disabled="!selectedPayment || selectedPayment.status !== 'PLANNED'"
            :loading="acting"
            @click="generatePreview"
          >
            生成建议方案
          </el-button>
          <el-button
            v-if="isOwner"
            type="warning"
            :disabled="!selectedPayment || selectedPayment.status !== 'ALLOCATED'"
            :loading="acting"
            @click="applyOverride"
          >
            应用手动调整
          </el-button>
          <el-button
            v-if="isOwner"
            type="success"
            :disabled="!selectedPayment || selectedPayment.status !== 'ALLOCATED'"
            :loading="acting"
            @click="confirmReservation"
          >
            确认预留
          </el-button>
        </div>
      </div>
    </template>

    <div v-loading="loading" style="min-height: 200px">
    <template v-if="selectedPayment">
      <el-row :gutter="12" class="stat-row">
        <el-col :span="8">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">付款金额</div>
            <div class="stat-value">¥{{ fmt(selectedPayment.amount) }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">当前状态</div>
            <div class="stat-value">
              <el-tag :type="(statusTag[selectedPayment.status] ?? 'info') as any">
                {{ statusLabel[selectedPayment.status] }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">分配总额</div>
            <div class="stat-value" :class="{ warn: !totalMatches }">
              ¥{{ fmt(totalAllocated) }}
              <span v-if="!totalMatches" class="stat-hint">（应等于付款金额）</span>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Funding source bar -->
      <div class="viz-block">
        <div class="block-title">资金拆分</div>
        <div class="funding-track">
          <div
            v-for="(seg, i) in segments"
            :key="i"
            class="funding-seg"
            :style="{ width: (seg.value / Number(selectedPayment.amount)) * 100 + '%', background: seg.color }"
            :title="seg.accountId ? `${accountName(seg.accountId)}: ¥${fmt(seg.value)}` : `未覆盖: ¥${fmt(seg.value)}`"
          />
        </div>
        <div class="funding-legend">
          <span v-for="(seg, i) in segments" :key="i" class="legend-item">
            <span class="dot" :style="{ background: seg.color }" />
            {{ seg.accountId ? accountName(seg.accountId) : '未覆盖' }}
            ¥{{ fmt(seg.value) }}
          </span>
        </div>
      </div>

      <!-- Per-account capacity bars -->
      <div class="viz-block">
        <div class="block-title">各账户资金容量</div>
        <div v-for="(acc, i) in allocatable" :key="acc.id" class="acc-row">
          <div class="acc-info">
            <div class="acc-name">
              {{ acc.name }}
              <el-tag
                v-if="reservedMap[acc.id]"
                type="warning"
                size="small"
                class="reserved-tag"
              >
                已预留 ¥{{ fmt(reservedMap[acc.id]) }}
              </el-tag>
            </div>
            <div class="acc-nums">
              可用 <b>{{ fmt(acc.planning_available) }}</b>
              · 最低留存 {{ fmt(acc.minimum_balance) }}
              · 余额 {{ fmt(acc.actual_balance) }}
            </div>
          </div>
          <div class="acc-bar-wrap">
            <div class="acc-bar-track">
              <div
                class="acc-bar-fill"
                :style="{
                  width: percent(Number(edits[acc.id] || 0), acc.planning_available) + '%',
                  background: accountColor(i),
                }"
              />
              <div
                v-if="Number(edits[acc.id] || 0) > Number(acc.planning_available)"
                class="acc-bar-over"
              />
            </div>
          </div>
          <el-input-number
            v-model="edits[acc.id]"
            :precision="2"
            :min="0"
            :step="100"
            :disabled="!isOwner || selectedPayment.status !== 'ALLOCATED'"
            controls-position="right"
            class="acc-input"
            :placeholder="'可分配 ¥' + fmt(acc.planning_available)"
          />
        </div>
        <el-empty
          v-if="allocatable.length === 0"
          description="没有参与分配的账户"
          :image-size="60"
        />
      </div>

      <el-alert type="info" :closable="false" class="safety-note">
        确认预留只做<strong>虚拟预留</strong>，不会动任何真实资金。真实转账请在你的银行 App / 网银完成，然后在付款页标记「已人工执行」。
      </el-alert>
    </template>

    <el-empty v-else description="暂无待分配 / 已分配 / 已预留的付款计划" />
    </div>
  </el-card>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.opt-sub {
  float: right;
  color: #909399;
  font-size: 12px;
  margin-left: 12px;
}
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
}
.stat-label {
  color: #909399;
  font-size: 13px;
}
.stat-value {
  font-size: 22px;
  font-weight: 600;
  margin-top: 4px;
}
.stat-value.warn {
  color: #f56c6c;
}
.stat-hint {
  font-size: 12px;
  color: #f56c6c;
  font-weight: 400;
}
.viz-block {
  margin-bottom: 20px;
}
.block-title {
  font-weight: 600;
  margin-bottom: 10px;
}
.funding-track {
  display: flex;
  height: 34px;
  border-radius: 6px;
  overflow: hidden;
  background: #f0f2f5;
}
.funding-seg {
  height: 100%;
  transition: width 0.3s ease;
}
.funding-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 8px;
  font-size: 13px;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  display: inline-block;
}
.acc-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.acc-info {
  width: 240px;
  flex-shrink: 0;
}
.acc-name {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}
.acc-nums {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.reserved-tag {
  font-weight: 400;
}
.acc-bar-wrap {
  flex: 1;
}
.acc-bar-track {
  position: relative;
  height: 16px;
  border-radius: 8px;
  background: #f0f2f5;
  overflow: hidden;
}
.acc-bar-fill {
  height: 100%;
  border-radius: 8px;
  transition: width 0.3s ease;
}
.acc-bar-over {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    45deg,
    #f56c6c55,
    #f56c6c55 6px,
    transparent 6px,
    transparent 12px
  );
}
.acc-input {
  width: 170px;
  flex-shrink: 0;
}
.safety-note {
  margin-top: 8px;
}
</style>
