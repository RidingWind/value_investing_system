<template>
  <div class="params-container">
    <el-row :gutter="20">
      <!-- 左侧分类树 -->
      <el-col :span="6">
        <el-tree
          :data="categoryTree"
          node-key="key"
          :props="treeProps"
          @node-click="handleCategoryClick"
          highlight-current
          default-expand-all
        />
      </el-col>

      <!-- 右侧参数表格 -->
      <el-col :span="18">
        <el-table :data="filteredParams" border stripe v-loading="loading">
          <el-table-column prop="key" label="参数Key" width="240" />
          <el-table-column label="当前值" width="200">
            <template #default="{ row }">
              <span :style="{ color: row.value === row.default_value ? '#333' : '#E6A23C' }">
                {{ formatValue(row.value) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="80" />
          <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
          <el-table-column label="热更新" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.hot_reloadable ? 'success' : 'info'" size="small">
                {{ row.hot_reloadable ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="openEditDialog(row)">编辑</el-button>
              <el-button size="small" @click="openHistoryDialog(row.key)">历史</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-col>
    </el-row>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="修改参数" width="500px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="参数Key">
          <el-input :model-value="editForm.key" disabled />
        </el-form-item>
        <el-form-item label="当前值">
          <el-tag>{{ formatValue(editForm.currentValue) }}</el-tag>
        </el-form-item>
        <el-form-item label="新值" required>
          <!-- 根据类型动态渲染 -->
          <el-input-number v-if="editForm.type === 'int' || editForm.type === 'float'"
                           v-model="editForm.newValue" :precision="editForm.type === 'float' ? 2 : 0" />
          <el-input v-else-if="editForm.type === 'str'" v-model="editForm.newValue" />
          <el-input v-else-if="editForm.type === 'list' || editForm.type === 'dict'"
                    v-model="editForm.newValue" type="textarea" :rows="3"
                    placeholder="请输入合法JSON" />
          <el-switch v-else-if="editForm.type === 'bool'" v-model="editForm.newValue" />
          <el-input v-else v-model="editForm.newValue" />
        </el-form-item>
        <el-form-item label="修改原因" required>
          <el-input v-model="editForm.reason" type="textarea" :rows="2" placeholder="请填写修改原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- 变更历史对话框 -->
    <el-dialog v-model="historyDialogVisible" title="变更历史" width="800px">
      <el-table :data="historyList" border max-height="400">
        <el-table-column prop="timestamp" label="时间" width="180" :formatter="formatTime" />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="value" label="变更后值" min-width="200">
          <template #default="{ row }">
            <span :class="{ 'text-mono': true }">{{ formatValue(row.value) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row, $index }">
            <el-button
              size="small"
              type="warning"
              :disabled="$index === 0"
              @click="confirmRollback(row)"
            >
              回滚
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 回滚确认对话框 -->
    <el-dialog v-model="rollbackDialogVisible" title="确认回滚" width="450px">
      <el-alert
        title="回滚操作将把参数值恢复到历史版本，请谨慎操作"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-form :model="rollbackForm" label-width="100px" style="margin-top: 16px;">
        <el-form-item label="参数Key">
          <el-tag>{{ rollbackForm.key }}</el-tag>
        </el-form-item>
        <el-form-item label="回滚到值">
          <el-tag type="warning">{{ formatValue(rollbackForm.value) }}</el-tag>
        </el-form-item>
        <el-form-item label="当前值">
          <el-tag>{{ formatValue(rollbackForm.currentValue) }}</el-tag>
        </el-form-item>
        <el-form-item label="回滚原因" required>
          <el-input v-model="rollbackForm.reason" type="textarea" :rows="2" placeholder="请填写回滚原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rollbackDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="rolling" @click="executeRollback">确认回滚</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

// 状态
const loading = ref(false)
const saving = ref(false)
const allParams = ref([])
const selectedCategory = ref(null)
const editDialogVisible = ref(false)
const historyDialogVisible = ref(false)
const editForm = ref({})
const historyList = ref([])
const rollbackDialogVisible = ref(false)
const rolling = ref(false)
const rollbackForm = ref({ key: '', value: null, currentValue: null, reason: '' })
const currentRollbackKey = ref('')
const treeProps = { children: 'children', label: 'label' }

// 分类树定义（与后端 scope 对应）
const categoryTree = [
  { key: 'business', label: '业务参数', children: [] },
  { key: 'technical', label: '技术参数', children: [] }
  // 市场参数也归入business或单独，可根据scope字段动态展开
]

// 根据 selectedCategory 过滤
const filteredParams = computed(() => {
  if (!selectedCategory.value) return allParams.value
  return allParams.value.filter(p => p.scope === selectedCategory.value.key)
})

// 加载所有参数
const loadParams = async () => {
  loading.value = true
  try {
    const { data } = await axios.get('/api/v1/params')
    allParams.value = data
  } catch (error) {
    ElMessage.error('参数加载失败')
  } finally {
    loading.value = false
  }
}

// 点击树节点
const handleCategoryClick = (node) => {
  selectedCategory.value = node
}

// 打开编辑对话框
const openEditDialog = (row) => {
  editForm.value = {
    key: row.key,
    currentValue: row.value,
    type: row.type,
    newValue: row.type === 'bool' ? row.value : JSON.stringify(row.value),
    reason: ''
  }
  editDialogVisible.value = true
}

// 提交修改
const submitEdit = async () => {
  if (!editForm.value.reason) {
    ElMessage.warning('请填写修改原因')
    return
  }
  let newValue = editForm.value.newValue
  if (['int', 'float'].includes(editForm.value.type)) newValue = Number(newValue)
  else if (['list', 'dict'].includes(editForm.value.type)) {
    try { newValue = JSON.parse(newValue) } catch { ElMessage.error('JSON格式错误'); return }
  }

  saving.value = true
  try {
    await axios.put(`/api/v1/params/${editForm.value.key}`, {
      value: newValue,
      reason: editForm.value.reason
    })
    ElMessage.success('参数更新成功，已实时生效')
    editDialogVisible.value = false
    loadParams() // 刷新列表
  } catch (error) {
    ElMessage.error('更新失败：' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const confirmRollback = (historyRow) => {
  // 获取当前参数值
  const currentParam = allParams.value.find(p => p.key === currentRollbackKey.value)
  rollbackForm.value = {
    key: currentRollbackKey.value,
    value: historyRow.value,
    currentValue: currentParam?.value,
    reason: ''
  }
  rollbackDialogVisible.value = true
}

const executeRollback = async () => {
  if (!rollbackForm.value.reason) {
    ElMessage.warning('请填写回滚原因')
    return
  }
  rolling.value = true
  try {
    await axios.put(`/api/v1/params/${rollbackForm.value.key}`, {
      value: rollbackForm.value.value,
      reason: `[回滚] ${rollbackForm.value.reason}`
    })
    ElMessage.success('参数已回滚至历史版本')
    rollbackDialogVisible.value = false
    historyDialogVisible.value = false
    loadParams() // 刷新参数列表
  } catch (error) {
    ElMessage.error('回滚失败：' + (error.response?.data?.detail || error.message))
  } finally {
    rolling.value = false
  }
}

// 查看历史
const openHistoryDialog = async (key) => {
  currentRollbackKey.value = key
  try {
    const { data } = await axios.get(`/api/v1/params/${key}/history`)
    historyList.value = data
    historyDialogVisible.value = true
  } catch {
    ElMessage.error('加载历史失败')
  }
}

// 工具函数
const formatValue = (value) => {
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
const formatTime = (row) => {
  if (!row.timestamp) return ''
  return new Date(row.timestamp * 1000).toLocaleString()
}

onMounted(loadParams)
</script>
