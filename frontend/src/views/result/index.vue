<template>
  <section class="page" data-module="result">
    <header class="page-head">
      <div>
        <h2>检测结果管理</h2>
        <p class="page-desc">判定结论由系统按检出限与评价标准自动生成：低于检出限按未检出处理，超标给出具体偏离范围；检测员不再手填结论。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检测结果</button>
        <button class="btn" type="button" @click="rejudgeAll">按当前规则全部重判</button>
        <button class="btn" type="button" @click="exportRows">导出检测结果清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>结果编号</span>
        <input v-model="filters.keyword" placeholder="按结果编号检索" />
      </label>
      <label class="filter-item">
        <span>结果状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>判定结论</span>
        <select v-model="filters.conclusion">
          <option value="">全部</option>
          <option v-for="c in conclusions" :key="c" :value="c">{{ c }}</option>
        </select>
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
          <td>{{ row['结果编号'] ?? '—' }}</td>
          <td>{{ row['关联任务'] ?? '—' }}</td>
          <td>{{ row['检测项目'] ?? '—' }}</td>
          <td>{{ row['检测值'] ?? '—' }}</td>
          <td>{{ row['检出限'] ?? '—' }}</td>
          <td>{{ row['评价标准'] ?? '—' }}</td>
          <td>
            <span v-if="snapshot(row)?.结论" :class="['conclusion-tag', tagClass(snapshot(row)?.结论)]">
              {{ snapshot(row)?.结论 }}
            </span>
            <span v-else class="conclusion-tag unresolved">未判定</span>
            <div v-if="snapshot(row)?.失败原因" class="cell-reason">{{ snapshot(row)?.失败原因 }}</div>
            <div v-else-if="snapshot(row)?.偏离范围" class="cell-reason danger">{{ snapshot(row)?.偏离范围 }}</div>
          </td>
          <td>{{ row['结果状态'] ?? row.status ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openEdit(row)">录入/修正数据</button>
            <button class="link" type="button" @click="rejudgeRow(row)">重新判定</button>
            <button class="link" type="button" @click="showBasis(row)">判定依据</button>
            <button class="link" type="button" @click="runAction('提交复核', row)">提交复核</button>
            <button class="link" type="button" @click="runAction('退回修正', row)">退回修正</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无检测结果数据，可先登记检测结果</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检测结果记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="infoMessage" class="info-text">{{ infoMessage }}</span>
    </footer>

    <!-- 录入 / 修正检测数据 -->
    <div v-if="editing" class="modal-mask" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? '录入/修正检测数据' : '登记检测结果' }}</h3>
        <p class="modal-tip">保存即按当前判定规则自动给出结论并冻结判定依据；已复核结果改动后会退回待复核。</p>
        <div v-for="field in editFields" :key="field" class="form-row">
          <label>
            <span>{{ field }}</span>
            <input v-model="editing[field]" :placeholder="field" />
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="editing = null">取消</button>
          <button class="btn primary" type="button" @click="saveEdit">保存并自动判定</button>
        </div>
      </div>
    </div>

    <!-- 判定依据（复核人看到的冻结快照） -->
    <div v-if="basisRow" class="modal-mask" @click.self="basisRow = null">
      <div class="modal wide">
        <h3>判定依据 · {{ basisRow['结果编号'] }}</h3>
        <p class="modal-tip">以下内容为该结果判定时冻结的快照，复核人看到的依据与录入时完全一致；规则改动后需重新判定才会更新。</p>
        <table class="data-table basis-table">
          <tbody>
            <tr v-for="item in basisRows" :key="item.label">
              <th>{{ item.label }}</th>
              <td :class="{ danger: item.danger }">{{ item.value ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="basisRow = null">知道了</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>
type Snapshot = {
  结论?: string | null
  判定说明?: string | null
  失败原因?: string | null
  偏离范围?: string | null
  判定依据?: string | null
  规则编号?: string | null
  规则版本?: number | null
  限值?: string | null
  参与比对数值?: string | null
  比对检出限?: string | null
  检测值原文?: string | null
  检出限原文?: string | null
  判定时间?: string | null
}

const ENDPOINT = '/api/result'
const columns = ['结果编号', '关联任务', '检测项目', '检测值', '检出限', '评价标准', '判定结论', '结果状态']
const statuses = ['待录入', '待复核', '已复核', '已退回']
const conclusions = ['合格', '不合格', '合格（未检出）', '未判定']
const editFields = ['结果编号', '关联任务', '检测项目', '评价标准', '检测值', '检出限']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const infoMessage = ref('')
const filters = reactive<Record<string, string>>({ keyword: '', status: '', conclusion: '' })
const editing = ref<Row | null>(null)
const basisRow = ref<Row | null>(null)

const stats = computed(() => {
  const count = (pred: (s: Snapshot | undefined) => boolean) =>
    rows.value.filter((row) => pred(snapshotOf(row))).length
  return [
    { label: '合格结果', value: count((s) => s?.结论 === '合格' || s?.结论 === '合格（未检出）') },
    { label: '不合格结果', value: count((s) => s?.结论 === '不合格') },
    { label: '未判定结果', value: count((s) => !s?.结论) },
    { label: '待复核结果', value: rows.value.filter((r) => r.status === '待复核').length },
  ]
})

const basisRows = computed(() => {
  const s: Snapshot = basisRow.value?.judge_snapshot ?? {}
  return [
    { label: '判定结论', value: s.结论 ?? `未判定（${s.失败原因 ?? ''}）`, danger: !s.结论 || s.结论 === '不合格' },
    { label: '判定依据', value: s.判定依据 ?? '—' },
    { label: '判定说明', value: s.判定说明 ?? '—' },
    { label: '偏离范围', value: s.偏离范围 ?? '未偏离 / 未判定', danger: !!s.偏离范围 },
    { label: '适用规则', value: s.规则编号 ? `${s.规则编号}（v${s.规则版本}）` : '未匹配到规则' },
    { label: '评价标准限值', value: s.限值 ?? '—' },
    { label: '检出限', value: s.比对检出限 ?? '—' },
    { label: '参与比对数值', value: s.参与比对数值 ?? '—' },
    { label: '检测值原文', value: s.检测值原文 ?? '—' },
    { label: '检出限原文', value: s.检出限原文 ?? '—' },
    { label: '判定时间', value: s.判定时间 ?? '—' },
  ]
})

function snapshotOf(row: Row): Snapshot | undefined {
  return row.judge_snapshot as Snapshot | undefined
}
function snapshot(row: Row): Snapshot | undefined {
  return snapshotOf(row)
}
function tagClass(conclusion?: string | null) {
  if (conclusion === '不合格') return 'unqualified'
  if (conclusion === '合格') return 'qualified'
  if (conclusion === '合格（未检出）') return 'not-detected'
  return ''
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  filters.conclusion = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  editing.value = { 结果编号: '', 关联任务: '', 检测项目: '', 评价标准: '', 检测值: '', 检出限: '' }
}

function openEdit(row: Row) {
  editing.value = { ...Object.fromEntries(editFields.map((f) => [f, row[f] ?? ''])), id: row.id }
}

async function saveEdit() {
  errorMessage.value = ''
  const target = editing.value
  if (!target) return
  const id = target.id
  const payload: Record<string, any> = {}
  editFields.forEach((f) => { payload[f] = target[f] })
  const url = id ? `${ENDPOINT}/${id}` : ENDPOINT
  const method = id ? 'PUT' : 'POST'
  try {
    const response = await request(url, { method, body: JSON.stringify({ values: payload }) })
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.message ?? '保存失败')
    infoMessage.value = data.message
    editing.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测结果保存失败'
  }
}

async function rejudgeRow(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/rejudge`, { method: 'POST' })
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.message ?? '重新判定失败')
    infoMessage.value = data.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重新判定失败'
  }
}

async function rejudgeAll() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/rejudge/all`, { method: 'POST' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.message ?? '全部重判失败')
    infoMessage.value = data.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '全部重判失败'
  }
}

function showBasis(row: Row) {
  basisRow.value = row
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.message ?? '检测结果动作未生效')
    infoMessage.value = data.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测结果操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.status) params.set('status', filters.status)
  if (filters.conclusion) params.set('conclusion', filters.conclusion)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) throw new Error('检测结果列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测结果列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.conclusion-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  white-space: nowrap;
}
.conclusion-tag.qualified { background: #e6f4ea; color: #1e7e34; }
.conclusion-tag.not-detected { background: #e8f0fe; color: #1a56db; }
.conclusion-tag.unqualified { background: #fde8e8; color: #b42318; }
.conclusion-tag.unresolved { background: #f2f4f7; color: #667085; }
.cell-reason { font-size: 12px; color: #667085; margin-top: 2px; max-width: 260px; }
.cell-reason.danger { color: #b42318; }
.info-text { color: #1a56db; }
.modal-mask {
  position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 20;
}
.modal {
  background: #fff; border-radius: 10px; padding: 20px 24px;
  width: 460px; max-height: 86vh; overflow: auto;
}
.modal.wide { width: 680px; }
.modal h3 { margin: 0 0 4px; font-size: 16px; }
.modal-tip { color: #667085; font-size: 12px; margin: 0 0 12px; }
.form-row label { display: block; margin-bottom: 10px; }
.form-row span { display: block; font-size: 12px; color: #667085; margin-bottom: 4px; }
.form-row input { width: 100%; box-sizing: border-box; padding: 6px 8px; border: 1px solid #d0d5dd; border-radius: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.basis-table th { width: 130px; background: #f9fafb; }
.basis-table .danger { color: #b42318; }
</style>
