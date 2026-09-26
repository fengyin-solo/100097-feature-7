<template>
  <section class="page" data-module="judge-rule">
    <header class="page-head">
      <div>
        <h2>判定规则管理</h2>
        <p class="page-desc">按「检测项目 + 评价标准」固化合格口径；同一检测项目在不同标准下可各配一条。限值改动自动升版本，并把同口径的既有结果重新判一遍。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">新增判定规则</button>
      </div>
    </header>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键词</span>
        <input v-model="filters.keyword" placeholder="规则编号 / 检测项目 / 评价标准" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td>{{ row['规则编号'] }}</td>
          <td>{{ row['检测项目'] }}</td>
          <td>{{ row['评价标准'] }}</td>
          <td>{{ row['标准编号'] ?? '—' }}</td>
          <td>{{ row['下限值'] ?? '—' }}</td>
          <td>{{ row['上限值'] ?? '—' }}</td>
          <td>{{ row['单位'] ?? '—' }}</td>
          <td>v{{ row['版本号'] }}</td>
          <td>
            <span :class="['status-tag', row['状态'] === '启用' ? 'on' : 'off']">{{ row['状态'] }}</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openEdit(row)">编辑限值</button>
            <button class="link" type="button" @click="toggle(row)">{{ row['状态'] === '启用' ? '停用' : '启用' }}</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无判定规则，请先按检测项目与评价标准登记限值口径</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条判定规则；规则保存后同口径既有结果会自动重判，结论变化的已复核结果退回待复核</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="infoMessage" class="info-text">{{ infoMessage }}</span>
    </footer>

    <div v-if="editing" class="modal-mask" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? '编辑判定规则' : '新增判定规则' }}</h3>
        <p class="modal-tip">同一检测项目+评价标准只能有一条启用规则；上限值、下限值至少填一项（限值不含等号外的边界，等于限值判合格）。</p>
        <div v-for="field in editFields" :key="field.key" class="form-row">
          <label>
            <span>{{ field.label }}</span>
            <input v-model="editing[field.key]" :placeholder="field.placeholder ?? field.label" />
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="editing = null">取消</button>
          <button class="btn primary" type="button" @click="save">保存并重判同口径结果</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/judge-rule'
const columns = ['规则编号', '检测项目', '评价标准', '标准编号', '下限值', '上限值', '单位', '版本', '状态']
const editFields = [
  { key: '规则编号', label: '规则编号' },
  { key: '检测项目', label: '检测项目（须与结果录入名称完全一致）' },
  { key: '评价标准', label: '评价标准（区分同一项目的不同口径）' },
  { key: '标准编号', label: '标准编号' },
  { key: '下限值', label: '下限值（无则留空）', placeholder: '如 6.5' },
  { key: '上限值', label: '上限值（无则留空）', placeholder: '如 8.5' },
  { key: '单位', label: '单位', placeholder: '如 mg/L、无量纲' },
  { key: '备注', label: '备注' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const infoMessage = ref('')
const filters = reactive({ keyword: '' })
const editing = ref<Row | null>(null)

function resetFilters() {
  filters.keyword = ''
  void reload()
}

function openCreate() {
  editing.value = { 规则编号: '', 检测项目: '', 评价标准: '', 标准编号: '', 下限值: '', 上限值: '', 单位: '', 备注: '' }
}

function openEdit(row: Row) {
  editing.value = { ...row }
}

async function save() {
  errorMessage.value = ''
  const target = editing.value
  if (!target) return
  const payload: Record<string, any> = {}
  editFields.forEach((f) => { payload[f.key] = target[f.key] ?? '' })
  const id = target.id
  const url = id ? `${ENDPOINT}/${id}` : ENDPOINT
  const method = id ? 'PUT' : 'POST'
  try {
    const response = await request(url, { method, body: JSON.stringify({ values: payload }) })
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.message ?? '规则保存失败')
    infoMessage.value = data.message
    editing.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '规则保存失败'
  }
}

async function toggle(row: Row) {
  errorMessage.value = ''
  const action = row['状态'] === '启用' ? '停用' : '启用'
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.message ?? '状态切换失败')
    infoMessage.value = data.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '状态切换失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.keyword) params.set('keyword', filters.keyword)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) throw new Error('判定规则列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '判定规则列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.status-tag.on { background: #e6f4ea; color: #1e7e34; }
.status-tag.off { background: #f2f4f7; color: #667085; }
.info-text { color: #1a56db; }
.modal-mask {
  position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 20;
}
.modal {
  background: #fff; border-radius: 10px; padding: 20px 24px;
  width: 500px; max-height: 86vh; overflow: auto;
}
.modal h3 { margin: 0 0 4px; font-size: 16px; }
.modal-tip { color: #667085; font-size: 12px; margin: 0 0 12px; }
.form-row label { display: block; margin-bottom: 10px; }
.form-row span { display: block; font-size: 12px; color: #667085; margin-bottom: 4px; }
.form-row input { width: 100%; box-sizing: border-box; padding: 6px 8px; border: 1px solid #d0d5dd; border-radius: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
</style>
