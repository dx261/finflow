<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { ForecastResponse } from '@/types'

const data = ref<ForecastResponse | null>(null)
const days = ref(30)
const loading = ref(true)

function money(value: string): number {
  return Number(value)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await api.get<ForecastResponse>('/forecast', { params: { days: days.value } })
    data.value = res.data
    render()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function render(): void {
  const el = document.getElementById('forecast-chart')
  if (!el || !data.value) return
  const chart = echarts.init(el)
  const agg = data.value.aggregate
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['预测余额', '收入', '支出'] },
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: agg.map((d) => d.date) },
    yAxis: { type: 'value' },
    series: [
      {
        name: '预测余额',
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.15 },
        data: agg.map((d) => money(d.ending_balance)),
      },
      { name: '收入', type: 'bar', data: agg.map((d) => money(d.expected_income)) },
      { name: '支出', type: 'bar', data: agg.map((d) => money(d.expected_expense)) },
    ],
  })
}

onMounted(load)
watch(days, load)
</script>

<template>
  <div v-loading="loading">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>现金流预测</span>
          <el-radio-group v-model="days">
            <el-radio-button :value="7">7 天</el-radio-button>
            <el-radio-button :value="30">30 天</el-radio-button>
            <el-radio-button :value="90">90 天</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div id="forecast-chart" style="height: 400px" />
    </el-card>

    <el-card class="mt-16">
      <template #header>低余额预警</template>
      <el-table v-if="data && data.warnings.length" :data="data.warnings" size="small">
        <el-table-column prop="account_id" label="账户" width="120">
          <template #default="{ row }">{{ row.account_id.slice(0, 8) }}</template>
        </el-table-column>
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column label="预计余额" width="140" align="right">
          <template #default="{ row }">¥{{ row.projected_balance }}</template>
        </el-table-column>
        <el-table-column label="最低保留" width="140" align="right">
          <template #default="{ row }">¥{{ row.minimum_balance }}</template>
        </el-table-column>
      </el-table>
      <el-alert
        v-else
        type="success"
        :closable="false"
        title="未来预测期内没有账户会跌破最低保留资金"
      />
    </el-card>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mt-16 {
  margin-top: 16px;
}
</style>
