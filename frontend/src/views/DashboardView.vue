<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getInstanceByDom, init, type EChartsType } from '@/lib/charts'
import { api, errorMessage } from '@/api/client'
import type { Account, ForecastResponse, PaymentPlan } from '@/types'
import { ElMessage } from 'element-plus'

const accounts = ref<Account[]>([])
const forecast = ref<ForecastResponse | null>(null)
const upcoming = ref<PaymentPlan[]>([])
const overdue = ref<PaymentPlan[]>([])
const loading = ref(true)
const charts: EChartsType[] = []
const chartCurrency = ref('CNY')

function resizeCharts(): void {
  charts.forEach((chart) => chart.resize())
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  charts.forEach((chart) => chart.dispose())
})

const totals = ref<Record<string, { actual: number; planning: number; reserved: number }>>({})

function money(value: string): number {
  return Number(value)
}

onMounted(async () => {
  window.addEventListener('resize', resizeCharts)
  try {
    const [accRes, fcRes, payRes] = await Promise.all([
      api.get<Account[]>('/accounts'),
      api.get<ForecastResponse>('/forecast', { params: { days: 30 } }),
      api.get<PaymentPlan[]>('/payments'),
    ])
    accounts.value = accRes.data
    forecast.value = fcRes.data
    const today = new Date().toISOString().slice(0, 10)
    const activeStatuses = ['PLANNED', 'ALLOCATED', 'RESERVED', 'WAITING_MANUAL_EXECUTION']
    upcoming.value = payRes.data.filter(
      (p) => activeStatuses.includes(p.status) && p.planned_date >= today,
    )
    overdue.value = payRes.data.filter(
      (p) => activeStatuses.includes(p.status) && p.planned_date < today,
    )

    totals.value = accounts.value.reduce<Record<string, { actual: number; planning: number; reserved: number }>>(
      (result, account) => {
        result[account.currency] ??= { actual: 0, planning: 0, reserved: 0 }
        result[account.currency].actual += money(account.actual_balance)
        result[account.currency].planning += money(account.planning_available)
        result[account.currency].reserved += money(account.reserved_amount)
        return result
      },
      {},
    )
    chartCurrency.value = fcRes.data.aggregate_currency ?? Object.keys(fcRes.data.aggregates_by_currency)[0] ?? 'CNY'

    renderForecastChart()
    renderDistributionChart()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
})

function renderForecastChart(): void {
  const el = document.getElementById('forecast-chart')
  if (!el || !forecast.value) return
  const chart = getInstanceByDom(el) ?? init(el)
  if (!charts.includes(chart)) charts.push(chart)
  const days = forecast.value.aggregates_by_currency[chartCurrency.value] ?? forecast.value.aggregate
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['预测余额', '最低线'] },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: days.map((d) => d.date.slice(5)) },
    yAxis: { type: 'value' },
    series: [
      {
        name: '预测余额',
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.15 },
        data: days.map((d) => money(d.ending_balance)),
      },
    ],
  })
}

function renderDistributionChart(): void {
  const el = document.getElementById('distribution-chart')
  if (!el || accounts.value.length === 0) return
  const chart = getInstanceByDom(el) ?? init(el)
  if (!charts.includes(chart)) charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        label: { formatter: '{b}: {d}%' },
        data: accounts.value
          .filter((a) => a.currency === chartCurrency.value)
          .map((a) => ({ name: a.name, value: money(a.actual_balance) })),
      },
    ],
  })
}

const statusTag: Record<string, string> = {
  PLANNED: 'primary',
  ALLOCATED: 'warning',
  RESERVED: 'warning',
  WAITING_MANUAL_EXECUTION: 'danger',
  MANUALLY_EXECUTED: 'info',
}
const statusLabel: Record<string, string> = {
  PLANNED: '待分配',
  ALLOCATED: '待确认预留',
  RESERVED: '已预留',
  WAITING_MANUAL_EXECUTION: '待人工付款',
  MANUALLY_EXECUTED: '待对账',
}
</script>

<template>
  <div v-loading="loading">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">账户总余额</div>
          <div v-for="(item, currency) in totals" :key="currency" class="stat-value">
            {{ currency }} {{ item.actual.toFixed(2) }}
          </div></el-card
        >
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">可规划资金</div>
          <div v-for="(item, currency) in totals" :key="currency" class="stat-value stat-green">
            {{ currency }} {{ item.planning.toFixed(2) }}
          </div></el-card
        >
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">虚拟预占</div>
          <div v-for="(item, currency) in totals" :key="currency" class="stat-value stat-orange">
            {{ currency }} {{ item.reserved.toFixed(2) }}
          </div></el-card
        >
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">待付款计划</div>
          <div class="stat-value">{{ upcoming.length }} 笔</div>
          <div v-if="overdue.length" class="overdue">另有 {{ overdue.length }} 笔已逾期</div></el-card
        >
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-16">
      <el-col :span="16">
        <el-card>
          <template #header>30 日现金流预测（{{ chartCurrency }}）</template>
          <div id="forecast-chart" style="height: 320px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>余额分布（{{ chartCurrency }}）</template>
          <div id="distribution-chart" style="height: 320px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt-16">
      <template #header>即将到来的付款</template>
      <el-table :data="upcoming" size="small">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="planned_date" label="计划日期" width="120" />
        <el-table-column label="金额" width="140">
          <template #default="{ row }">{{ row.currency }} {{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="状态" width="180">
          <template #default="{ row }">
            <el-tag :type="(statusTag[row.status] ?? 'info') as any" size="small">{{
              statusLabel[row.status] ?? row.status
            }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="upcoming.length === 0" description="暂无即将到来的付款" />
    </el-card>
  </div>
</template>

<style scoped>
.stat-card {
  text-align: center;
}
.stat-label {
  color: #909399;
  font-size: 13px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  margin-top: 6px;
}
.stat-green {
  color: #67c23a;
}
.stat-orange {
  color: #e6a23c;
}
.overdue {
  margin-top: 4px;
  color: #f56c6c;
  font-size: 12px;
}
.mt-16 {
  margin-top: 16px;
}
</style>
