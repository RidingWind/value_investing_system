<template>
  <div>
    <h2>财务数据配置</h2>
    <el-tabs v-model="activeTab">
      <!-- 指标管理 -->
      <el-tab-pane label="指标管理" name="indicators">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-tree :data="indicatorTree" node-key="id" @node-click="handleTreeClick" default-expand-all />
          </el-col>
          <el-col :span="18">
            <el-card v-if="currentIndicator">
              <el-form label-width="120px">
                <el-form-item label="标准字段">
                  <el-input v-model="currentIndicator.standard_field" />
                </el-form-item>
                <el-form-item label="中文名称">
                  <el-input v-model="currentIndicator.chinese_name" />
                </el-form-item>
                <el-form-item label="数据类型">
                  <el-select v-model="currentIndicator.data_type">
                    <el-option value="float" />
                    <el-option value="int" />
                    <el-option value="str" />
                  </el-select>
                </el-form-item>
                <el-form-item label="单位">
                  <el-input v-model="currentIndicator.unit" />
                </el-form-item>
                <el-form-item label="报表分组">
                  <el-select
                    v-model="currentIndicator.report_group"
                    allow-create
                    filterable
                  >
                    <el-option
                      v-for="group in reportGroupOptions"
                      :key="group"
                      :label="group"
                      :value="group"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="计算公式" class="formula-editor">
                  <textarea v-model="currentIndicator.formula" rows="4" class="monaco-mock" />
                  <div class="dep-info">
                    依赖的API：
                    <el-tag v-for="dep in formulaDeps" :key="dep.function_name + dep.column_name" size="small">
                      {{ dep.function_name }}.{{ dep.column_name }}
                    </el-tag>
                    <span v-if="formulaDeps.length === 0" style="color: #999">无</span>
                  </div>
                </el-form-item>
                <el-form-item label="依赖绑定">
                  <div>
                    <el-button type="info" size="small" @click="addDepRow">添加依赖</el-button>
                    <div v-for="(dep, idx) in currentDeps" :key="idx" style="display:flex; align-items:center; margin-top:5px;">
                      <el-select
                        v-model="dep.api_id"
                        placeholder="选择API"
                        size="small"
                        style="width:200px;"
                        filterable
                        @change="onDepApiChange(idx)"
                      >
                        <el-option
                          v-for="api in availableApis"
                          :key="api.id"
                          :label="api.function_name + (api.chinese_name ? ' (' + api.chinese_name + ')' : '')"
                          :value="api.id"
                          :disabled="!api.output_columns || api.output_columns.length === 0"
                        />
                      </el-select>
                      <span style="margin: 0 8px;">.</span>
                      <el-select
                        v-model="dep.column_name"
                        placeholder="选择列"
                        size="small"
                        style="width:200px;"
                        filterable
                      >
                        <el-option
                          v-for="col in getApiColumns(dep.api_id)"
                          :key="col"
                          :label="col"
                          :value="col"
                        />
                      </el-select>
                      <el-button type="danger" size="small" :icon="Delete" circle @click="removeDepRow(idx)" style="margin-left:8px;" />
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="saveIndicator">保存</el-button>
                  <el-button @click="deleteCurrentIndicator" :disabled="!currentIndicator.id">删除</el-button>
                </el-form-item>
              </el-form>
            </el-card>
            <el-button type="success" @click="addIndicator" style="margin-top: 10px">新增指标</el-button>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- API 管理 -->
      <el-tab-pane label="API 管理" name="apis">
        <el-button type="primary" @click="addApiDialog = true" style="margin-bottom: 10px">新增 API</el-button>
        <el-table :data="apiList" border>
          <el-table-column prop="function_name" label="函数名" width="200" />
          <el-table-column prop="chinese_name" label="中文名" />
          <el-table-column prop="source" label="数据源" width="100" />
          <el-table-column label="输入参数" width="200">
            <template #default="{ row }">
              <el-popover placement="bottom" trigger="hover" :width="300">
                <pre style="max-height:200px;overflow:auto">{{ JSON.stringify(row.input_params, null, 2) }}</pre>
                <template #reference>
                  <span class="param-preview">{{ JSON.stringify(row.input_params) }}</span>
                </template>
              </el-popover>
            </template>
          </el-table-column>
          <el-table-column label="输出列" min-width="250">
            <template #default="{ row }">
              <template v-if="row.output_columns && row.output_columns.length">
                <el-tag
                  v-for="col in row.output_columns"
                  :key="col"
                  size="small"
                  style="margin-right:4px;margin-bottom:4px;"
                >{{ col }}</el-tag>
              </template>
              <span v-else style="color: #999">未获取</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260">
            <template #default="scope">
              <el-button size="small" @click="editApi(scope.row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteApi(scope.row.id)">删除</el-button>
              <el-button size="small" type="primary" @click="refreshApiColumns(scope.row)">刷新列</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 新增/编辑 API 对话框 -->
        <el-dialog v-model="addApiDialog" title="新增/编辑 API" width="600px">
          <el-form :model="apiForm" label-width="120px">
            <el-form-item label="函数名">
              <el-input v-model="apiForm.function_name" />
              <el-button size="small" @click="probeApi" style="margin-left: 10px">探测列名</el-button>
            </el-form-item>
            <el-form-item label="中文名">
              <el-input v-model="apiForm.chinese_name" />
            </el-form-item>
            <el-form-item label="输入参数">
              <el-input v-model="apiForm.input_params_str" type="textarea" :rows="2" placeholder='{"symbol":"{em_symbol}"}' />
            </el-form-item>
            <el-form-item label="日期列名">
              <el-input v-model="apiForm.date_column" />
            </el-form-item>
            <el-form-item label="筛选条件">
              <el-input v-model="apiForm.filter_condition" />
            </el-form-item>
            <el-form-item label="输出列">
              <el-tag v-for="col in apiForm.output_columns" :key="col" style="margin: 3px">{{ col }}</el-tag>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="addApiDialog = false">取消</el-button>
            <el-button type="primary" @click="saveApi">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- 依赖分析 -->
      <el-tab-pane label="依赖分析" name="deps">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-card header="按API查看受影响指标">
              <el-select v-model="selectedApiId" placeholder="选择API" @change="loadAffected">
                <el-option v-for="api in apiList" :key="api.id" :label="api.function_name" :value="api.id" />
              </el-select>
              <el-table :data="affectedIndicators" border style="margin-top: 10px" max-height="400">
                <el-table-column prop="standard_field" label="标准字段" />
                <el-table-column prop="chinese_name" label="中文名" />
                <el-table-column prop="column_name" label="依赖列" />
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card header="按指标查看依赖API">
              <el-select v-model="selectedIndicatorId" placeholder="选择指标" @change="loadDeps">
                <el-option v-for="ind in allIndicators" :key="ind.id" :label="ind.standard_field" :value="ind.id" />
              </el-select>
              <el-table :data="indicatorDeps" border style="margin-top: 10px" max-height="400">
                <el-table-column prop="function_name" label="API函数" />
                <el-table-column prop="column_name" label="依赖列" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

const activeTab = ref('indicators')
const apiList = ref([])
const allIndicators = ref([])
const indicatorTree = ref([])
const currentIndicator = ref(null)
const formulaDeps = ref([])

const selectedApiId = ref(null)
const affectedIndicators = ref([])
const selectedIndicatorId = ref(null)
const indicatorDeps = ref([])
// 当前编辑指标的依赖列表
const currentDeps = ref([])

const addApiDialog = ref(false)
const apiForm = ref({
  id: null,
  function_name: '',
  chinese_name: '',
  input_params_str: '{"symbol":"{em_symbol}"}',
  date_column: 'REPORT_DATE',
  filter_condition: '',
  output_columns: []
})

const reportGroupName = {
  income: '利润表',
  balance: '资产负债表',
  cashflow: '现金流量表',
  indicator: '主要财务指标'
}

// 从已加载的指标列表中提取所有分组，去重后排序
const reportGroupOptions = computed(() => {
  const groups = allIndicators.value.map(ind => ind.report_group).filter(Boolean)
  return [...new Set(groups)].sort()
})

// 所有已注册的 API（用于下拉选择）
const availableApis = computed(() => {
  return apiList.value
})

// ---------- 加载数据 ----------
const loadApis = async () => {
  const { data } = await axios.get('/api/v1/financial/config/apis')
  apiList.value = data.map(api => ({...api, input_params_str: JSON.stringify(api.input_params)}))
}

const loadIndicators = async () => {
  const { data } = await axios.get('/api/v1/financial/config/indicators')
  allIndicators.value = data
  // 构建树
  const groups = {}
  for (const ind of data) {
    const g = ind.report_group || 'other'
    if (!groups[g]) groups[g] = { label: reportGroupName[g] || g, children: [] }
    groups[g].children.push({
      label: `${ind.standard_field} (${ind.chinese_name})`,
      id: ind.id,
      data: ind
    })
  }
  indicatorTree.value = Object.values(groups)
}

// ---------- 指标操作 ----------
const handleTreeClick = (node) => {
  if (node.data) {
    currentIndicator.value = {...node.data}
    parseFormulaDeps()
    loadCurrentDeps(node.data.id)   // 新增：加载依赖
  }
}

// 加载指标的现有依赖
const loadCurrentDeps = async (indicatorId) => {
  if (!indicatorId) return
  try {
    const { data } = await axios.get(`/api/v1/financial/config/indicators/${indicatorId}/deps`)
    // 后端返回 [{function_name, column_name, api_id}, ...]
    currentDeps.value = data.map(d => ({
      api_id: d.api_id,
      column_name: d.column_name
    }))
  } catch {
    currentDeps.value = []
  }
}

// 添加依赖行
const addDepRow = () => {
  currentDeps.value.push({ api_id: null, column_name: '' })
}

// 删除依赖行
const removeDepRow = (idx) => {
  currentDeps.value.splice(idx, 1)
}
// 根据 api_id 获取该 API 的输出列
const getApiColumns = (apiId) => {
  const api = availableApis.value.find(a => a.id === apiId)
  return api?.output_columns || []
}

// 当 API 改变时，清空已选的列
const onDepApiChange = (idx) => {
  currentDeps.value[idx].column_name = ''
}

const parseFormulaDeps = () => {
  if (!currentIndicator.value || !currentIndicator.value.formula) {
    formulaDeps.value = []
    return
  }
  // 简单前端解析：匹配 api('func').col('col') 模式
  const pattern = /api\('(\w+)'\)\.col\('(\w+)'\)/g
  const deps = []
  let match
  while ((match = pattern.exec(currentIndicator.value.formula)) !== null) {
    deps.push({ function_name: match[1], column_name: match[2] })
  }
  formulaDeps.value = deps
}

watch(() => currentIndicator.value?.formula, parseFormulaDeps)

const saveIndicator = async () => {
  try {
    const payload = {
      ...currentIndicator.value,
      deps: currentDeps.value.filter(d => d.api_id && d.column_name)  // 只提交有效的依赖
    }
    await axios.post('/api/v1/financial/config/indicators', payload)
    ElMessage.success('保存成功')
    loadIndicators()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  }
}

const deleteCurrentIndicator = async () => {
  try {
    await ElMessageBox.confirm('确定删除该指标？')
    await axios.delete(`/api/v1/financial/config/indicators/${currentIndicator.value.id}`)
    ElMessage.success('已删除')
    currentIndicator.value = null
    loadIndicators()
  } catch (e) {}
}

const addIndicator = () => {
  currentIndicator.value = {
    standard_field: '',
    chinese_name: '',
    data_type: 'float',
    unit: '',
    report_group: 'indicator',
    formula: ''
  }
  currentDeps.value = []   // 重置依赖
}

// ---------- API 操作 ----------
const refreshApiColumns = async (apiRow) => {
  try {
    const { data } = await axios.post(`/api/v1/financial/config/apis/${apiRow.id}/refresh-columns`)
    apiRow.output_columns = data.columns   // 直接更新本地数组
    ElMessage.success(`成功获取 ${data.columns.length} 列`)
  } catch (e) {
    ElMessage.error('获取列失败: ' + (e.response?.data?.detail || e.message))
  }
}

const editApi = (row) => {
  apiForm.value = {...row, input_params_str: JSON.stringify(row.input_params)}
  addApiDialog.value = true
}

const deleteApi = async (id) => {
  try {
    await ElMessageBox.confirm('删除此API将同时删除依赖该API的指标关联，确定继续？')
    const res = await axios.delete(`/api/v1/financial/config/apis/${id}`)
    ElMessage.success('已删除，受影响的指标：' + res.data.affected_indicators?.map(i => i.standard_field).join(', '))
    loadApis()
  } catch (e) {}
}

const probeApi = async () => {
  try {
    const { data } = await axios.post(`/api/v1/financial/config/apis/probe?function_name=${apiForm.value.function_name}`,
      JSON.stringify(apiForm.value.input_params_str))
    apiForm.value.output_columns = data.columns
  } catch (e) {
    ElMessage.error('探测失败：' + (e.response?.data?.detail || e.message))
  }
}

const saveApi = async () => {
  try {
    const payload = {
      ...apiForm.value,
      input_params: JSON.parse(apiForm.value.input_params_str || '{}')
    }
    delete payload.input_params_str
    await axios.post('/api/v1/financial/config/apis', payload)
    ElMessage.success('保存成功')
    addApiDialog.value = false
    loadApis()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  }
}

// ---------- 依赖分析 ----------
const loadAffected = async () => {
  if (!selectedApiId.value) return
  const { data } = await axios.get(`/api/v1/financial/config/deps/affected/${selectedApiId.value}`)
  affectedIndicators.value = data
}

const loadDeps = async () => {
  if (!selectedIndicatorId.value) return
  const { data } = await axios.get(`/api/v1/financial/config/indicators/${selectedIndicatorId.value}/deps`)
  indicatorDeps.value = data
}

onMounted(() => {
  loadApis()
  loadIndicators()
})
</script>

<style scoped>
.monaco-mock {
  width: 100%;
  font-family: 'Courier New', Courier, monospace;
  background: #f5f5f5;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 8px;
}
.dep-info {
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}
.param-preview {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
  display: inline-block;
  cursor: pointer;
  color: #409eff;
}
</style>
