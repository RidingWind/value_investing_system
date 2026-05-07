<template>
  <div class="financial-container">
    <h2>财务数据管理</h2>

    <!-- 数据总览 -->
    <el-row :gutter="20" class="mt-20">
      <el-col :span="6" v-for="card in summaryCards" :key="card.label">
        <el-card>
          <template #header>{{ card.label }}</template>
          <div class="card-value">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 股票财务数据区间查询 -->
    <el-card class="mt-20">
      <template #header>查询股票财务数据区间</template>
      <el-input v-model="querySymbol" placeholder="输入股票代码（如000001.SZ）" clearable @keyup.enter="searchRange" style="width: 300px;" @input="querySymbol = querySymbol.toUpperCase()" />
      <el-button type="primary" @click="searchRange" class="ml-10">查询</el-button>
      <div v-if="rangeResult" class="range-info mt-10">
        <p><strong>代码：</strong>{{ rangeResult.symbol }}</p>
        <p><strong>数据区�：</strong>{{ rangeResult.start_date || '无' }} 至 {{ rangeResult.end_date || '无' }}</p>
        <p><strong>记录数：</strong>{{ rangeResult.record_count }}</p>
      </div>
      <div v-else-if="rangeSearched" class="mt-10 text-gray">未找到该股票的财务数据。</div>
    </el-card>

    <!-- 手动补全财务数据 -->
    <el-card class="mt-20">
      <template #header>手动补全财务数据</template>
      <div>
        <el-input v-model="fetchSymbols" placeholder="股票代码列表，逗号分隔" style="width: 400px;"  @input="fetchSymbols = fetchSymbols.toUpperCase()" />
        <el-select v-model="fetchQuarters" placeholder="季度数" class="ml-10" style="width: 120px;">
          <el-option label="1季度" :value="1" />
          <el-option label="2季度" :value="2" />
          <el-option label="4季度" :value="4" />
          <el-option label="6季度" :value="6" />
          <el-option label="8季度" :value="8" />
          <el-option label="12季度" :value="12" />
        </el-select>
        <el-button type="success" @click="triggerFetch" class="ml-10" :loading="fetching">开始采集</el-button>
      </div>
      <div v-if="fetchResult" class="mt-10">
        <p>{{ fetchResult.message }}</p>
        <el-table :data="fetchResult.details" border size="small" class="mt-10" v-if="fetchResult.details?.length">
          <el-table-column prop="symbol" label="股票代码" width="120" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="income" label="利润表" width="80" />
          <el-table-column prop="balance" label="资产负债表" width="100" />
          <el-table-column prop="cashflow" label="现金流" width="80" />
          <el-table-column prop="indicator" label="指标" width="80" />
          <el-table-column prop="error" label="错误" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>

    <!-- 采集历史日志 -->
    <el-card class="mt-20">
      <template #header>
        <span>最近采集记录（最近 {{ logLimit }} 条）</span>
        <el-button size="small" style="float: right;" @click="loadLogs">刷新</el-button>
      </template>
      <el-table :data="logs" border max-height="300">
        <el-table-column prop="symbol" label="股票代码" width="120" />
        <el-table-column prop="periods" label="季度数" width="80" />
        <el-table-column prop="stored" label="入库数" width="80" />
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">
            {{ row.timestamp?.slice(0, 19) || '' }}
          </template>
        </el-table-column>
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
    const { data } = await axios.get('/api/v1/financial/summary')
    summaryCards.value = [
      { label: '利润表记录', value: data.income_records },
      { label: '资产负债表记录', value: data.balance_records },
      { label: '现金流量记录', value: data.cashflow_records },
      { label: '财务指标记录', value: data.indicator_records },
    ]
  } catch { ElMessage.error('加载总览失败') }
}

// 股票区间查询
const querySymbol = ref('')
const rangeResult = ref(null)
const rangeSearched = ref(false)
const searchRange = async () => {
  if (!querySymbol.value) return
  rangeSearched.value = true
  try {
    const { data } = await axios.get(`/api/v1/financial/range/${querySymbol.value}`)
    rangeResult.value = data
  } catch {
    rangeResult.value = null
  }
}

// 手动补全
const fetchSymbols = ref('')
const fetchQuarters = ref(6)
const fetching = ref(false)
const fetchResult = ref(null)
const triggerFetch = async () => {
  if (!fetchSymbols.value) { ElMessage.warning('请输入股票代码'); return }
  const symbols = fetchSymbols.value.split(',').map(s => s.trim()).filter(Boolean)
  if (!symbols.length) { ElMessage.warning('请输入有效的股票代码'); return }
  fetching.value = true
  fetchResult.value = null
  try {
    const { data } = await axios.post('/api/v1/financial/fetch', {
      symbols,
      quarters: fetchQuarters.value
    })
    fetchResult.value = data
    ElMessage.success(data.message)
    loadSummary()
    loadLogs()
  } catch (e) {
    ElMessage.error('采集失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    fetching.value = false
  }
}

// 日志
const logs = ref([])
const logLimit = 20
const loadLogs = async () => {
  try {
    const { data } = await axios.get(`/api/v1/financial/logs?limit=${logLimit}`)
    logs.value = data
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
.text-gray { color: #999; }
</style>
