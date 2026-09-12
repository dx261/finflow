<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { api, errorMessage } from '@/api/client'
import type { Account, ForecastResponse, PaymentPlan } from '@/types'
import { ElMessage } from 'element-plus'

const accounts = ref<Account[]>([])
const forecast = ref<ForecastResponse | null>(null)
const upcoming = ref<PaymentPlan[]>([])
const loading = ref(true)

const totals = {
  actual: 0,
  planning: 0,
  reserved: 0,
}

function money(value: string): number {
  return Number(value)
}

onMounted(async () => {
  try {
    const [accRes, fcRes, payRes] = await Promise.all([
      api.get<Account[]>('/accounts'),
      api.get<ForecastResponse>('/forecast', { params: { days: 30 } }),
      api.get<PaymentPlan[]>('/payments'),
    ])
    accounts.value = accRes.data
    forecast.value = fcRes.data
    upcoming.value = payRes.data.filter((p) =>
      ['PLANNED', 'RESERVED', 'WAITING_MANUAL_EXECUTION'].includes(p.status),
    )

    totals.actual = accounts.value.reduce((sum, a) => sum + money(a.actual_balance), 0)
    totals.planning = accounts.value.reduce((sum, a) => sum + money(a.planning_available), 0)
    totals.reserved = accounts.value.reduce((sum, a) => sum + money(a.reserved_amount), 0)

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
  const chart = echarts.init(el)
  const days = forecast.value.aggregate
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
  const chart = echarts.init(el)
  chart.setOption({
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        label: { formatter: '{b}: {d}%' },
        data: accounts.value.map((a) => ({ name: a.name, value: money(a.actual_balance) })),
      },
    ],
  })
}

const statusTag: Record<string, string> = {
  PLANNED: 'primary',
  RESERVED: 'warning',
  WAITING_MANUAL_EXECUTION: 'danger',
  MANUALLY_EXECUTED: 'info',
}
</script>

<template>
  <div v-loading="loading">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">账户总余额</div>
          <div class="stat-value">¥{{ totals.actual.toFixed(2) }}</div></el-card
        >
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">可规划资金</div>
          <div class="stat-value stat-green">¥{{ totals.planning.toFixed(2) }}</div></el-card
        >
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">虚拟预占</div>
          <div class="stat-value stat-orange">¥{{ totals.reserved.toFixed(2) }}</div></el-card
        >
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"
          ><div class="stat-label">待付款计划</div>
          <div class="stat-value">{{ upcoming.length }} 笔</div></el-card
        >
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-16">
      <el-col :span="16">
        <el-card>
          <template #header>30 日现金流预测</template>
          <div id="forecast-chart" style="height: 320px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>余额分布</template>
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
          <template #default="{ row }">¥{{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="状态" width="180">
          <template #default="{ row }">
            <el-tag :type="(statusTag[row.status] ?? 'info') as any" size="small">{{
              row.status
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
.mt-16 {
  margin-top: 16px;
}
</style>
