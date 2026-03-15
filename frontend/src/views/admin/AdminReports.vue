<template>
  <div>
    <h2>{{ t('admin.reportsTitle') }}</h2>

    <el-card class="mb16">
      <el-form :inline="true" :model="form" @submit.prevent>
        <el-form-item :label="t('admin.reportRange')">
          <el-date-picker
            v-model="form.range"
            type="daterange"
            range-separator="-"
            :start-placeholder="t('admin.start')"
            :end-placeholder="t('admin.end')"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item :label="t('admin.granularity')">
          <el-select v-model="form.granularity" style="width: 160px">
            <el-option :label="t('admin.day')" value="day" />
            <el-option :label="t('admin.week')" value="week" />
            <el-option :label="t('admin.month')" value="month" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">{{ t('admin.search') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="mb16">
      <el-col :span="6">
        <el-statistic :title="t('admin.totalSales')" :value="summary?.total_sales ?? 0" prefix="￥" />
      </el-col>
      <el-col :span="6">
        <el-statistic :title="t('admin.orderCount')" :value="summary?.order_count ?? 0" />
      </el-col>
    </el-row>

    <el-card class="mb16">
      <template #header>{{ t('admin.salesTrend') }}</template>
      <div ref="trendEl" class="chart" />
    </el-card>

    <el-card>
      <template #header>{{ t('admin.bestSellers') }}</template>
      <div ref="bestEl" class="chart" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import api from '../../api/http'
import { extractErrorMessage } from '../../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import { pickProductText } from '../../utils/productI18n'

type Granularity = 'day' | 'week' | 'month'

interface SalesSeriesPoint {
  period: string
  sales: number
  order_count: number
}

interface BestSeller {
  product_id: number
  title: string
  title_en?: string | null
  sales: number
}

interface SalesSummary {
  total_sales: number
  order_count: number
  best_sellers: BestSeller[]
  series: SalesSeriesPoint[]
}

const { t, locale } = useI18n()

const form = ref<{ range: [string, string] | null; granularity: Granularity }>(
  {
    range: null,
    granularity: 'day',
  }
)

const summary = ref<SalesSummary | null>(null)
const trendEl = ref<HTMLDivElement | null>(null)
const bestEl = ref<HTMLDivElement | null>(null)

let trendChart: echarts.ECharts | null = null
let bestChart: echarts.ECharts | null = null

function pickTitle(zh?: string | null, en?: string | null) {
  return pickProductText(zh, en, String(locale.value))
}

const trendPeriods = computed(() => summary.value?.series?.map((p) => p.period) || [])
const trendSales = computed(() => summary.value?.series?.map((p) => p.sales) || [])
const trendOrders = computed(() => summary.value?.series?.map((p) => p.order_count) || [])

const bestNames = computed(() => (summary.value?.best_sellers || []).map((b) => pickTitle(b.title, b.title_en)))
const bestSales = computed(() => (summary.value?.best_sellers || []).map((b) => b.sales))

function toYmd(d: Date) {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

function defaultRange(): [string, string] {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 29)
  return [toYmd(start), toYmd(end)]
}

async function load() {
  try {
    const params: any = { granularity: form.value.granularity }
    const range = form.value.range || defaultRange()
    params.start = range[0]
    params.end = range[1]
    const { data } = await api.get('/api/admin/reports/sales', { params })
    summary.value = data
    await nextTick()
    renderCharts()
  } catch (e: any) {
    ElMessage.error(extractErrorMessage(e, t('msg.loadFailed')))
  }
}

function ensureCharts() {
  if (trendEl.value && !trendChart) trendChart = echarts.init(trendEl.value)
  if (bestEl.value && !bestChart) bestChart = echarts.init(bestEl.value)
}

function renderCharts() {
  ensureCharts()
  if (!trendChart || !bestChart) return

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('admin.totalSales'), t('admin.orderCount')] },
    grid: { left: 40, right: 40, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: trendPeriods.value },
    yAxis: [
      { type: 'value', name: t('admin.totalSales') },
      { type: 'value', name: t('admin.orderCount') },
    ],
    series: [
      { name: t('admin.totalSales'), type: 'line', data: trendSales.value, smooth: true },
      { name: t('admin.orderCount'), type: 'bar', yAxisIndex: 1, data: trendOrders.value, barMaxWidth: 24 },
    ],
  })

  bestChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 120, right: 40, top: 20, bottom: 40 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: bestNames.value.slice().reverse() },
    series: [
      {
        name: t('admin.totalSales'),
        type: 'bar',
        data: bestSales.value.slice().reverse(),
        barMaxWidth: 24,
      },
    ],
  })
}

function handleResize() {
  trendChart?.resize()
  bestChart?.resize()
}

onMounted(async () => {
  form.value.range = defaultRange()
  await load()
  window.addEventListener('resize', handleResize)
})

watch(
  () => String(locale.value),
  () => {
    // 语言切换后重绘图表标题/图例
    renderCharts()
  }
)
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
}

.chart {
  width: 100%;
  height: 360px;
}
</style>
