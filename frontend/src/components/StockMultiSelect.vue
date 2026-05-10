<template>
  <el-select
    v-model="selected"
    multiple
    filterable
    remote
    reserve-keyword
    placeholder="输入代码/名称/拼音搜索，可多选"
    :remote-method="remoteSearch"
    :loading="loading"
    style="width: 100%"
  >
    <el-option
      v-for="item in options"
      :key="item.value"
      :label="item.label"
      :value="item.value"
    />
  </el-select>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

// 内部维护选中值，与 v-model 双向绑定
const selected = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const options = ref([])
const loading = ref(false)

const remoteSearch = async (query) => {
  if (!query || query.length < 1) {
    options.value = []
    return
  }
  loading.value = true
  try {
    const { data } = await axios.get('/api/v1/search/stocks', {
      params: { keyword: query }
    })
    options.value = data.map(item => ({
      label: `${item.standard_code} ${item.name}`,
      value: item.standard_code
    }))
  } catch (e) {
    options.value = []
  } finally {
    loading.value = false
  }
}
</script>
