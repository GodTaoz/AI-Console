<script setup lang="ts">
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { computed } from 'vue'

import { language, theme } from '@/stores/ui'
import type { MetricPoint } from '@/types'

export interface ChartSeries {
  name: string
  unit: 'percent' | 'bytes_per_second' | string
  points: MetricPoint[]
}

const props = withDefaults(defineProps<{ series: ChartSeries[]; height?: number; kind?: 'line' | 'bar'; ariaLabel: string }>(), {
  height: 260,
  kind: 'line',
})

use([LineChart, BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const root = ref<HTMLDivElement | null>(null)
const hasData = computed(() => props.series.some((item) => item.points.length))
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

function token(name: string, fallback: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function formatValue(value: number, unit: string) {
  if (unit === 'percent') return `${value.toFixed(1)}%`
  if (unit === 'bytes_per_second') {
    const units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
    let scaled = value
    let index = 0
    while (scaled >= 1024 && index < units.length - 1) { scaled /= 1024; index += 1 }
    return `${scaled.toFixed(index ? 1 : 0)} ${units[index]}`
  }
  return value.toLocaleString(language.value)
}

function render() {
  if (!chart) return
  const colors = [token('--chart-1', '#5b8f6a'), token('--chart-2', '#c28a3c'), token('--chart-3', '#668db0'), token('--chart-4', '#bd6d6d')]
  const option: EChartsCoreOption = {
    animationDuration: 280,
    color: colors,
    aria: { enabled: true, label: { description: props.ariaLabel } },
    grid: { left: 10, right: 12, top: props.series.length > 1 ? 38 : 16, bottom: 8, containLabel: true },
    legend: props.series.length > 1 ? { top: 0, right: 4, textStyle: { color: token('--text-soft', '#737b74') }, itemWidth: 14, itemHeight: 3 } : undefined,
    tooltip: {
      trigger: 'axis',
      backgroundColor: token('--surface-raised', '#fff'),
      borderColor: token('--border', '#ddd'),
      textStyle: { color: token('--text-strong', '#222') },
      valueFormatter: (value: unknown) => formatValue(Number(value), props.series[0]?.unit ?? ''),
    },
    xAxis: {
      type: 'time',
      boundaryGap: false,
      axisLine: { lineStyle: { color: token('--border', '#ddd') } },
      axisTick: { show: false },
      axisLabel: { color: token('--text-soft', '#777'), hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: props.series.every((item) => item.unit === 'percent') ? 0 : undefined,
      max: props.series.every((item) => item.unit === 'percent') ? 100 : undefined,
      axisLabel: { color: token('--text-soft', '#777'), formatter: (value: number) => formatValue(value, props.series[0]?.unit ?? '') },
      splitLine: { lineStyle: { color: token('--chart-grid', '#ddd'), type: 'dashed' } },
    },
    series: props.series.map((item, index) => ({
      name: item.name,
      type: props.kind,
      showSymbol: false,
      connectNulls: false,
      smooth: 0.18,
      lineStyle: { width: 1.8 },
      areaStyle: props.kind === 'line' ? { opacity: index === 0 ? 0.12 : 0.05 } : undefined,
      data: item.points.map((point) => [point.timestamp, point.value]),
    })),
  }
  chart.setOption(option, { notMerge: true })
}

onMounted(() => {
  if (!root.value) return
  chart = init(root.value)
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(root.value)
  render()
})
watch([() => props.series, theme, language], () => void nextTick(render), { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>

<template>
  <div class="metric-chart-shell" :style="{ height: `${height}px` }">
    <div ref="root" class="metric-chart" />
    <div v-if="!hasData" class="metric-chart__empty">—</div>
  </div>
</template>
