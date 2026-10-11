<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getInstanceByDom, init, type EChartsType } from '@/lib/charts'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '@/api/client'
import type { ForecastResponse } from '@/types'

const data = ref<ForecastResponse | null>(null)
const days = ref(30)
const selectedCurrency = ref('')
const loading = ref(true)
let chart: EChartsType | null = null

function resizeChart(): void {
  chart?.resize()
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
  chart = null
})

function money(value: string): number {
  return Number(value)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await api.get<ForecastResponse>('/forecast', { params: { days: days.value } })
    data.value = res.data
    const currencies = Object.keys(res.data.aggregates_by_currency)
    if (!currencies.includes(selectedCurrency.value)) {
      selectedCurrency.value = res.data.aggregate_currency ?? currencies[0] ?? ''
    }
    await nextTick()
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
  chart = getInstanceByDom(el) ?? init(el)
  const agg = data.value.aggregates_by_currency[selectedCurrency.value] ?? data.value.aggregate
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
onMounted(() => window.addEventListener('resize', resizeChart))
watch(days, load)
watch(selectedCurrency, () => render())

const currencies = computed(() => Object.keys(data.value?.aggregates_by_currency ?? {}))
</script>

<template>
  <div v-loading="loading">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>现金流预测</span>
          <div class="forecast-controls">
            <el-select
              v-if="currencies.length > 1"
              v-model="selectedCurrency"
              style="width: 110px"
              aria-label="预测币种"
            >
              <el-option v-for="currency in currencies" :key="currency" :label="currency" :value="currency" />
            </el-select>
            <el-radio-group v-model="days">
              <el-radio-button :value="7">7 天</el-radio-button>
              <el-radio-button :value="30">30 天</el-radio-button>
              <el-radio-button :value="90">90 天</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      <div id="forecast-chart" style="height: 400px" />
    </el-card>

    <el-card class="mt-16">
      <template #header>低余额预警</template>
      <el-table v-if="data && data.warnings.length" :data="data.warnings" size="small">
        <el-table-column prop="account_name" label="账户" min-width="140" />
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column label="预计余额" width="140" align="right">
          <template #default="{ row }">{{ row.currency }} {{ row.projected_balance }}</template>
        </el-table-column>
        <el-table-column label="最低保留" width="140" align="right">
          <template #default="{ row }">{{ row.currency }} {{ row.minimum_balance }}</template>
        </el-table-column>
      </el-table>
      <el-alert
        v-else
        type="success"
        :closable="false"
        title="未来预测期内没有账户会跌破最低保留资金"
      />
    </el-card>

    <el-card class="mt-16">
      <template #header>待归属现金流</template>
      <el-alert
        v-if="data?.unassigned.length"
        type="warning"
        :closable="false"
        title="以下项目尚未指定账户，因此不会改变任何账户的预测余额"
        class="unassigned-alert"
      />
      <el-table v-if="data?.unassigned.length" :data="data.unassigned" size="small">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="name" label="项目" min-width="180" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ row.flow_type === 'income' ? '收入' : '支出' }}</template>
        </el-table-column>
        <el-table-column label="金额" width="160" align="right">
          <template #default="{ row }">{{ row.currency }} {{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="来源" width="130">
          <template #default="{ row }">{{ row.source_type === 'PAYMENT' ? '付款计划' : '现金流计划' }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="所有预测项目都已归属到具体账户" :image-size="60" />
    </el-card>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.forecast-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.unassigned-alert {
  margin-bottom: 12px;
}
.mt-16 {
  margin-top: 16px;
}
</style>
