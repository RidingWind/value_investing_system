<template>
  <div class="market-data">
    <h2>行情数据管理</h2>

    <!-- 1. 数据库总览 -->
    <el-row :gutter="20">
      <el-col :span="6" v-for="card in summaryCards" :key="card.label">
        <el-card>
          <template #header>{{ card.label }}</template>
          <div class="card-value">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 2. 股票数据范围查询 -->
    <el-card class="mt-20">
      <template #header>查询股票数据区间</template>
      <el-input v-model="querySymbol" placeholder="输入股票代码（如000001.SZ）" clearable @keyup.enter="searchRange" style="width: 300px;" @input="querySymbol = querySymbol.toUpperCase()" />
      <el-button type="primary" @click="searchRange" class="ml-10">查询</el-button>
      <div v-if="rangeResult" class="range-info mt-10">
        <p>代码：{{ rangeResult.symbol }}</p>
        <p>数据区间：{{ rangeResult.start_date }} 至 {{ rangeResult.end_date }}</p>
        <p>记录数：{{ rangeResult.record_count }}</p>
      </div>
    </el-card>

    <!-- 3. 手动补全数据 -->
    <el-card class="mt-20">
      <template #header>手动补全行情</template>
      <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center;">
        <el-input
          v-model="fetchSymbols"
          placeholder="股票代码列表，逗号分隔（如 000001.SZ,600000.SH）"
          style="width: 320px;"
          clearable @input="querySymbol = querySymbol.toUpperCase()"
        />
        <el-date-picker
          v-model="fetchDateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 280px;"
        />
        <el-button type="success" @click="triggerFetch" :loading="fetching">
          <el-icon><Download /></el-icon>
          开始采集
        </el-button>
      </div>
      <div v-if="fetching" class="mt-10" style="color: #409eff;">
        <el-icon class="is-loading"><Loading /></el-icon> 正在采集，请稍候...
      </div>
      <div v-if="fetchResult" class="mt-10" style="color: #67c23a;">
        {{ fetchResult }}
      </div>
    </el-card>

    <!-- 采集历史日志（保留） -->
    <el-card class="mt-20">
      <template #header>最近采集记录（最近20条）</template>
      <el-table :data="logs" border max-height="300">
        <el-table-column prop="trigger" label="触发源" width="80" />
        <el-table-column prop="start_time" label="开始时间" width="160" />
        <el-table-column prop="status" label="状态" width="80" />
        <el-table-column prop="record_count" label="获取数" width="80" />
        <el-table-column prop="stored_count" label="入库数" width="80" />
        <el-table-column prop="error" label="错误" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 数据总览
const summaryCards = ref([])
const loadSummary = async () => {
  try {
    const { data } = await axios.get('/api/v1/market/summary')
    summaryCards.value = [
      { label: '总记录数', value: data.total_records },
      { label: '覆盖股票数', value: data.symbol_count },
      { label: '最早日期', value: data.start_date || '无' },
      { label: '最晚日期', value: data.end_date || '无' },
    ]
  } catch { ElMessage.error('加载总览失败') }
}

// 股票区间查询
const querySymbol = ref('')
const rangeResult = ref(null)
const searchRange = async () => {
  if (!querySymbol.value) return
  try {
    const { data } = await axios.get(`/api/v1/market/range/${querySymbol.value}`)
    rangeResult.value = data
  } catch { ElMessage.error('未找到该股票数据') }
}

// 手动补全
const fetchSymbols = ref('')
const fetchDateRange = ref([])
const fetching = ref(false)
const fetchResult = ref('')
const triggerFetch = async () => {
  if (!fetchSymbols.value) { ElMessage.warning('请输入股票代码'); return }
  const symbols = fetchSymbols.value.split(',').map(s => s.trim())
  const payload = { symbols }
  if (fetchDateRange.value && fetchDateRange.value.length === 2) {
    payload.start_date = fetchDateRange.value[0]
    payload.end_date = fetchDateRange.value[1]
  }
  fetching.value = true
  fetchResult.value = ''
  try {
    const { data } = await axios.post('/api/v1/market/fetch', payload)
    fetchResult.value = data.message
    ElMessage.success(data.message)
    loadSummary() // 刷新总览
    loadLogs()
  } catch (e) {
    ElMessage.error('采集失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    fetching.value = false
  }
}

// 日志
const logs = ref([])
const loadLogs = async () => {
  try {
    const { data } = await axios.get('/api/v1/market/logs?limit=20')
    logs.value = data.logs
  } catch {}
}

onMounted(() => {
  loadSummary()
  loadLogs()
})
</script>

<style scoped>
.mt-20 { margin-top: 20px; }
.ml-10 { margin-left: 10px; }
.card-value { font-size: 24px; font-weight: bold; color: #409eff; }
.range-info p { margin: 5px 0; }
</style>
