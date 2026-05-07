<template>
  <div class="audit-container">
    <!-- 筛选栏 -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :model="filterForm" inline>
        <el-form-item label="参数Key">
          <el-select v-model="filterForm.key" clearable filterable placeholder="全部" style="width: 280px;">
            <el-option v-for="key in allParamKeys" :key="key" :label="key" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作人">
          <el-input v-model="filterForm.operator" clearable placeholder="操作人" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadAuditLogs">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 审计日志表格 -->
    <el-card shadow="never">
      <template #header>
        <span>操作审计日志（共 {{ total }} 条）</span>
        <el-button size="small" style="float: right;" @click="exportLogs" :disabled="logs.length === 0">
          <el-icon><Download /></el-icon> 导出CSV
        </el-button>
      </template>
      <el-table :data="logs" border stripe v-loading="loading" max-height="600">
        <el-table-column prop="timestamp" label="时间" width="180" :formatter="formatTime" />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="key" label="参数Key" width="240" show-overflow-tooltip />
        <el-table-column prop="value" label="变更后值" min-width="250">
          <template #default="{ row }">
            <span :class="{ 'text-mono': true }">{{ formatValue(row.value) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="String(row.reason || '').startsWith('[回滚]')" type="warning" size="small">回滚</el-tag>
            <el-tag v-else type="primary" size="small">修改</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-if="total > 0"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadAuditLogs"
        @current-change="loadAuditLogs"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const logs = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const allParamKeys = ref([])

const filterForm = ref({
  key: '',
  operator: '',
  dateRange: null
})

const loadAuditLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterForm.value.key) params.key = filterForm.value.key
    if (filterForm.value.operator) params.operator = filterForm.value.operator
    if (filterForm.value.dateRange) {
      params.start_time = Math.floor(filterForm.value.dateRange[0].getTime() / 1000)
      params.end_time = Math.floor(filterForm.value.dateRange[1].getTime() / 1000)
    }
    const { data } = await axios.get('/api/v1/audit/logs', { params })
    logs.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('审计日志加载失败')
  } finally {
    loading.value = false
  }
}

const resetFilter = () => {
  filterForm.value = { key: '', operator: '', dateRange: null }
  currentPage.value = 1
  loadAuditLogs()
}

const exportLogs = () => {
  // 构造CSV导出
  const headers = ['时间', '操作人', '参数Key', '变更后值', '原因']
  const rows = logs.value.map(log => [
    formatTime({ timestamp: log.timestamp }),
    log.operator,
    log.key,
    formatValue(log.value),
    log.reason || ''
  ])
  let csvContent = headers.join(',') + '\n'
  rows.forEach(row => { csvContent += row.map(v => `"${v}"`).join(',') + '\n' })
  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `audit_logs_${new Date().toISOString().slice(0,10)}.csv`
  link.click()
}

const formatTime = (row) => {
  if (!row.timestamp) return ''
  return new Date(row.timestamp * 1000).toLocaleString()
}

const formatValue = (value) => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// 加载参数key列表用于筛选
const loadParamKeys = async () => {
  try {
    const { data } = await axios.get('/api/v1/params')
    allParamKeys.value = data.map(p => p.key)
  } catch {}
}

onMounted(() => {
  loadParamKeys()
  loadAuditLogs()
})
</script>

<style scoped>
.text-mono {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
}
</style>