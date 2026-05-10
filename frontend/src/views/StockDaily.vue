<template>
  <div class="stock-daily-container">
    <div class="header">
      <h2>{{ symbol }} 行情</h2>
      <div class="controls">
        <el-select v-model="freq" @change="fetchData" style="width: 120px">
          <el-option label="日线" value="daily" />
          <el-option label="周线" value="weekly" />
          <el-option label="月线" value="monthly" />
          <el-option label="年线" value="yearly" />
        </el-select>
        <el-select
          v-model="selectedIndicators"
          multiple
          placeholder="副图指标(最多2个)"
          :multiple-limit="2"
          @change="updateChart"
          style="width: 250px; margin-left: 10px"
        >
          <el-option label="成交量" value="VOL" />
          <el-option label="MACD" value="MACD" />
          <el-option label="KDJ" value="KDJ" />
          <el-option label="RSI" value="RSI" />
          <el-option label="BOLL" value="BOLL" />
        </el-select>
        <el-button @click="$router.go(-1)">返回</el-button>
      </div>
    </div>
    <div ref="chartRef" class="chart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import * as echarts from 'echarts'

const route = useRoute()
const symbol = ref(route.query.symbol || '')
const freq = ref('daily')
const selectedIndicators = ref(['VOL', 'MACD']) // 默认成交量和MACD
const chartRef = ref(null)
let chart = null
let rawData = [] // 缓存原始数据

// ---------- 指标计算函数 ----------
const calcMA = (data, period) => {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
    } else {
      let sum = 0
      for (let j = i - period + 1; j <= i; j++) sum += data[j].close
      result.push(sum / period)
    }
  }
  return result
}

const calcEMA = (data, period) => {
  const k = 2 / (period + 1)
  let ema = [data[0].close]
  for (let i = 1; i < data.length; i++) {
    ema.push(data[i].close * k + ema[i - 1] * (1 - k))
  }
  return ema
}

const calcMACD = (data, short = 12, long = 26, signal = 9) => {
  const emaShort = calcEMA(data, short)
  const emaLong = calcEMA(data, long)
  const dif = emaShort.map((v, i) => v - emaLong[i])
  const dea = []
  const histogram = []
  for (let i = 0; i < dif.length; i++) {
    if (i === 0) {
      dea.push(dif[0])
    } else {
      dea.push(dif[i] * (2 / (signal + 1)) + dea[i - 1] * (1 - 2 / (signal + 1)))
    }
    histogram.push(dif[i] - dea[i])
  }
  return { dif, dea, histogram }
}

const calcKDJ = (data, n = 9, m1 = 3, m2 = 3) => {
  const k = [], d = [], j = []
  for (let i = 0; i < data.length; i++) {
    if (i < n - 1) {
      k.push(null), d.push(null), j.push(null)
      continue
    }
    const slice = data.slice(i - n + 1, i + 1)
    const high = Math.max(...slice.map(v => v.high))
    const low = Math.min(...slice.map(v => v.low))
    const close = data[i].close
    const rsv = low === high ? 50 : ((close - low) / (high - low)) * 100
    const prevK = k[i - 1] ?? 50
    const prevD = d[i - 1] ?? 50
    const curK = (prevK * (m1 - 1) + rsv) / m1
    const curD = (prevD * (m2 - 1) + curK) / m2
    k.push(curK)
    d.push(curD)
    j.push(3 * curK - 2 * curD)
  }
  return { k, d, j }
}

const calcRSI = (data, period = 14) => {
  const gains = [], losses = [], rsi = []
  for (let i = 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close
    gains.push(diff > 0 ? diff : 0)
    losses.push(diff < 0 ? -diff : 0)
  }
  for (let i = period - 1; i < gains.length; i++) {
    let avgGain = gains.slice(i - period + 1, i + 1).reduce((a, b) => a + b) / period
    let avgLoss = losses.slice(i - period + 1, i + 1).reduce((a, b) => a + b) / period
    if (avgLoss === 0) rsi.push(100)
    else rsi.push(100 - 100 / (1 + avgGain / avgLoss))
  }
  return rsi
}

const calcBOLL = (data, period = 20, multiplier = 2) => {
  const mb = calcMA(data, period)
  const up = [], dn = []
  for (let i = 0; i < mb.length; i++) {
    if (mb[i] === null) {
      up.push(null), dn.push(null)
      continue
    }
    const slice = data.slice(i - period + 1, i + 1)
    const avg = mb[i]
    const variance = slice.reduce((sum, v) => sum + (v.close - avg) ** 2, 0) / period
    const std = Math.sqrt(variance)
    up.push(avg + multiplier * std)
    dn.push(avg - multiplier * std)
  }
  return { up, mb, dn }
}

// ---------- 构建图表 ----------
const updateChart = () => {
  if (!chart || !rawData.length) return

  const dates = rawData.map(v => v.trade_date)
  const volumes = rawData.map(v => v.volume || 0) // 成交量缺失补0
  const ma5 = calcMA(rawData, 5)
  const ma10 = calcMA(rawData, 10)
  const ma20 = calcMA(rawData, 20)
  const ma60 = calcMA(rawData, 60)

  const subIndicators = selectedIndicators.value.slice(0, 2) // 最多2个
  const hasVOL = subIndicators.includes('VOL')

  // 动态布局
  const gridCount = 1 + (hasVOL ? 1 : 0) + subIndicators.filter(s => s !== 'VOL').length
  const grids = []
  const xAxis = []
  const yAxis = []
  const series = []

  // 主图K线+MA+BOLL(如果选了BOLL)
  grids.push({ left: '10%', right: '10%', top: '5%', height: '45%' })
  xAxis.push({ type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } })
  yAxis.push({ type: 'value', gridIndex: 0, scale: true })

  series.push({
    name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
    data: rawData.map(v => [v.open, v.close, v.low, v.high]),
    itemStyle: { color: '#ef232a', color0: '#14b143' }
  })
  // MA线
  const maLines = [
    { name: 'MA5', data: ma5 },
    { name: 'MA10', data: ma10 },
    { name: 'MA20', data: ma20 },
    { name: 'MA60', data: ma60 }
  ]
  maLines.forEach(m => {
    series.push({ name: m.name, type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: m.data, smooth: true, lineStyle: { width: 1 } })
  })

  // 如果选中BOLL且不是副图（或放入副图），这里示例放在主图
  if (subIndicators.includes('BOLL')) {
    const boll = calcBOLL(rawData)
    series.push({ name: 'UP', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: boll.up, lineStyle: { width: 1, color: '#d4d4d4' } })
    series.push({ name: 'MB', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: boll.mb, lineStyle: { width: 1, color: '#d4d4d4' } })
    series.push({ name: 'DN', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: boll.dn, lineStyle: { width: 1, color: '#d4d4d4' } })
  }

  let gi = 1
  // 成交量副图（如果选中）
  if (hasVOL) {
    grids.push({ left: '10%', right: '10%', top: '52%', height: '10%' })
    xAxis.push({ type: 'category', data: dates, gridIndex: gi, axisLabel: { show: false } })
    yAxis.push({ type: 'value', gridIndex: gi, name: 'VOL', scale: true })
    series.push({
      name: '成交量', type: 'bar', xAxisIndex: gi, yAxisIndex: gi, data: volumes,
      itemStyle: { color: (params) => rawData[params.dataIndex].close >= rawData[params.dataIndex].open ? '#ef232a' : '#14b143' }
    })
    gi++
  }

  // 其他技术指标副图
  const nonVolIndicators = subIndicators.filter(s => s !== 'VOL' && s !== 'BOLL') // BOLL已放在主图
  nonVolIndicators.forEach(ind => {
    let subData = null
    let subSeries = []
    switch (ind) {
      case 'MACD': {
        const { dif, dea, histogram } = calcMACD(rawData)
        subData = { dif, dea, histogram }
        subSeries = [
          { name: 'DIF', type: 'line', data: dif },
          { name: 'DEA', type: 'line', data: dea },
          { name: 'MACD柱', type: 'bar', data: histogram }
        ]
        break
      }
      case 'KDJ': {
        const { k, d, j } = calcKDJ(rawData)
        subData = { k, d, j }
        subSeries = [
          { name: 'K', type: 'line', data: k },
          { name: 'D', type: 'line', data: d },
          { name: 'J', type: 'line', data: j }
        ]
        break
      }
      case 'RSI': {
        const rsi = calcRSI(rawData)
        subData = { rsi }
        subSeries = [{ name: 'RSI', type: 'line', data: rsi }]
        break
      }
    }
    if (subData) {
      const topPercent = (52 + (gi - 1) * 18) + '%'
      grids.push({ left: '10%', right: '10%', top: topPercent, height: '16%' })
      xAxis.push({ type: 'category', data: dates, gridIndex: gi, axisLabel: { show: true } })
      yAxis.push({ type: 'value', gridIndex: gi })
      subSeries.forEach(s => {
        series.push({ ...s, xAxisIndex: gi, yAxisIndex: gi, lineStyle: { width: 1 } })
      })
      gi++
    }
  })

  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: grids,
    xAxis: xAxis,
    yAxis: yAxis,
    series: series
  })
}

const fetchData = async () => {
  if (!symbol.value) return
  try {
    const { data } = await axios.get(`/api/v1/market/daily/${symbol.value}`, {
      params: { freq: freq.value }
    })
    if (!data?.data?.length) {
      console.warn('无数据')
      return
    }
    rawData = data.data
    updateChart()
  } catch (err) {
    console.error(err)
  }
}

onMounted(async () => {
  await nextTick()
  chart = echarts.init(chartRef.value)
  window.addEventListener('resize', () => chart?.resize())
  await fetchData()
})

watch(freq, () => {
  fetchData()
})
</script>

<style scoped>
.stock-daily-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 10px;
  background: #fff;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.chart {
  flex: 1;
  width: 100%;
  min-height: 400px;
}
</style>
