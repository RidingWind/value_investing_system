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
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
        <el-autocomplete
          v-model="querySymbol"
          :fetch-suggestions="searchStocks"
          placeholder="输入代码/名称/拼音"
          clearable
          style="width: 300px;"
          @select="handleSelectStock"
          @input="querySymbol = querySymbol.toUpperCase()"
        >
          <template #default="{ item }">
            <div class="stock-suggestion">
              <span class="code">{{ item.standard_code }}</span>
              <span class="name">{{ item.name }}</span>
            </div>
          </template>
        </el-autocomplete>
        <el-button type="primary" @click="searchRange" class="ml-10">查询</el-button>
      </div>
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
        <StockMultiSelect v-model="fetchSymbols" style="width: 400px" />
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
          <el-table-column label="利润表" width="100">
            <template #default="{ row }">
              <el-link type="primary" v-if="row.income > 0" @click="showDetail(row.symbol, 'income', row.indicator_details)">{{ row.income }} 条</el-link>
              <span v-else>0</span>
            </template>
          </el-table-column>
          <el-table-column label="资产负债表" width="100">
            <template #default="{ row }">
              <el-link type="primary" v-if="row.balance > 0" @click="showDetail(row.symbol, 'balance', row.indicator_details)">{{ row.balance }} 条</el-link>
              <span v-else>0</span>
            </template>
          </el-table-column>
          <el-table-column label="现金流" width="80">
            <template #default="{ row }">
              <el-link type="primary" v-if="row.cashflow > 0" @click="showDetail(row.symbol, 'cashflow', row.indicator_details)">{{ row.cashflow }} 条</el-link>
              <span v-else>0</span>
            </template>
          </el-table-column>
          <el-table-column label="指标" width="80">
            <template #default="{ row }">
              <el-link type="primary" v-if="row.indicator > 0" @click="showDetail(row.symbol, 'indicator', row.indicator_details)">{{ row.indicator }} 条</el-link>
              <span v-else>0</span>
            </template>
          </el-table-column>
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

  <el-dialog v-model="detailDialogVisible" :title="detailTitle" width="600px">
    <el-table :data="detailData" border max-height="400">
      <el-table-column prop="end_date" label="报告期" width="120" />
      <el-table-column prop="indicator_name" label="指标名称" width="200" />
      <el-table-column prop="value" label="值" />
    </el-table>
  </el-dialog>
</template>

<script setup>
import StockMultiSelect from '@/components/StockMultiSelect.vue'
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import {useRouter} from "vue-router";

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

const router = useRouter()

// 搜索建议函数
const searchStocks = async (queryString, callback) => {
  if (!queryString || queryString.length < 1) {
    callback([])
    return
  }
  try {
    const { data } = await axios.get('/api/v1/search/stocks', {
      params: { keyword: queryString }
    })
    // data 格式：[{ code, standard_code, name, pinyin }]
    const suggestions = data.map(item => ({
      value: item.standard_code,  // 选中的值
      standard_code: item.standard_code,
      name: item.name
    }))
    callback(suggestions)
  } catch {
    callback([])
  }
}

// 选中建议项时触发，可以自动填充并直接查询
const handleSelectStock = (item) => {
  querySymbol.value = item.standard_code
  // 可选：自动触发查询区间
  // searchRange()
}

// 新增：跳转到日线行情页面
const goToDailyChart = () => {
  if (!querySymbol.value) {
    ElMessage.warning('请选择股票代码')
    return
  }
  // 假设日线页面路由为 /stock/daily?symbol=000001.SZ
  router.push({ path: '/stock/daily', query: { symbol: querySymbol.value } })
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
const fetchSymbols = ref([])
const fetchQuarters = ref(6)
const fetching = ref(false)
const fetchResult = ref(null)
const triggerFetch = async () => {
  const symbols = fetchSymbols.value   // 已经是数组，如 ['000001.SZ', '600519.SH']
  if (!symbols || symbols.length === 0) {
    ElMessage.warning('请选择股票')
    return
  }
  if (!fetchQuarters.value) {
    ElMessage.warning('请选择季度数')
    return
  }
  fetching.value = true
  fetchResult.value = null
  try {
    const { data } = await axios.post('/api/v1/financial/fetch', {
      symbols,                     // 直接传数组
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
// const triggerFetch = async () => {
//   if (!fetchSymbols.value) { ElMessage.warning('请输入股票代码'); return }
//   const symbols = fetchSymbols.value.split(',').map(s => s.trim()).filter(Boolean)
//   if (!symbols.length) { ElMessage.warning('请输入有效的股票代码'); return }
//   fetching.value = true
//   fetchResult.value = null
//   try {
//     const { data } = await axios.post('/api/v1/financial/fetch', {
//       symbols,
//       quarters: fetchQuarters.value
//     })
//     fetchResult.value = data
//     ElMessage.success(data.message)
//     loadSummary()
//     loadLogs()
//   } catch (e) {
//     ElMessage.error('采集失败: ' + (e.response?.data?.detail || e.message))
//   } finally {
//     fetching.value = false
//   }
// }

// 日志
const logs = ref([])
const logLimit = 20
const loadLogs = async () => {
  try {
    const { data } = await axios.get(`/api/v1/financial/logs?limit=${logLimit}`)
    logs.value = data
  } catch {}
}

// 明细弹窗
const detailDialogVisible = ref(false)
const detailTitle = ref('')
const detailData = ref([])

const showDetail = (symbol, group, allDetails) => {
  // 从该股票的明细中筛选对应报表组的数据
  const filtered = allDetails.filter(item => item.report_group === group)
  detailData.value = filtered.map(item => ({
    end_date: item.end_date,
    indicator_name: item.indicator_name,
    value: item.value
  }))
  detailTitle.value = `${symbol} - ${group} 指标明细`
  detailDialogVisible.value = true
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
.stock-suggestion {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
.stock-suggestion .code {
  font-weight: bold;
  margin-right: 10px;
}
.stock-suggestion .name {
  color: #666;
}
</style>
