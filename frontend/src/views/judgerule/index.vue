<template>
  <section class="page" data-module="judgerule">
    <header class="page-head">
      <div>
        <h2>判定规则管理</h2>
        <p class="page-desc">按检测项目+评价标准固化判定口径（检出限、限量值）；修订规则会生成新版本，并把命中口径的既有检测结果自动重判一遍。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记判定规则</button>
        <button class="btn" type="button" @click="exportRows">导出判定规则清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="form-bar" @submit.prevent="submitCreate">
      <label v-for="field in createFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="createForm[field.key]" :placeholder="field.placeholder" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="keyword" placeholder="按规则编号、检测项目或评价标准检索" />
      </label>
      <label class="filter-item">
        <span>规则状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
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
          <td v-for="column in columns" :key="column">
            <span v-if="column === '规则状态'" class="tag" :class="row[column] === '现行有效' ? 'pass' : ''">
              {{ row[column] ?? '—' }}
            </span>
            <span v-else-if="column === '版本号'">v{{ row[column] }}</span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无判定规则数据，可先登记判定规则</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条判定规则记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="reviseRow" class="modal-mask" @click.self="reviseRow = null">
      <div class="modal-card">
        <h3>修订规则 · {{ reviseRow['规则编号'] }}（当前 v{{ reviseRow['版本号'] }}）</h3>
        <p class="modal-tip">修订后旧版本停用，命中「{{ reviseRow['检测项目'] }} · {{ reviseRow['评价标准'] }}」的既有检测结果将按新口径重判。</p>
        <form class="modal-form" @submit.prevent="submitRevise">
          <label v-for="field in reviseFields" :key="field" class="filter-item">
            <span>{{ field }}</span>
            <input v-model="reviseForm[field]" :placeholder="`新${field}`" />
          </label>
          <div class="modal-actions">
            <button class="btn primary" type="submit">提交修订并重判</button>
            <button class="btn ghost" type="button" @click="reviseRow = null">取消</button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, any>
type Page<T> = { items: T[]; total: number }
type ActionReply = { ok: boolean; message: string; entry: Row | null }

const ENDPOINT = '/api/judgerule'
const columns = ["规则编号", "检测项目", "评价标准", "检出限", "限量值", "单位", "版本号", "规则状态"]
const actions = ["修订规则", "重判结果", "停用规则"]
const statuses = ["现行有效", "已停用"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: "现行有效规则", value: 0 },
  { label: "已停用版本", value: 0 },
  { label: "覆盖检测项目", value: 0 },
])
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')

const showCreate = ref(false)
const createFields = [
  { key: "检测项目", label: "检测项目", placeholder: "如 铅（Pb）" },
  { key: "评价标准", label: "评价标准", placeholder: "如 GB 2762-2022 食品中污染物限量" },
  { key: "检出限", label: "检出限", placeholder: "数值，如 0.02" },
  { key: "限量值", label: "限量值", placeholder: "数值，如 0.5" },
  { key: "单位", label: "单位", placeholder: "如 mg/kg" },
]
const createForm = ref<Record<string, string>>({})

const reviseRow = ref<Row | null>(null)
const reviseFields = ["检出限", "限量值", "单位"]
const reviseForm = ref<Record<string, string>>({})

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  showCreate.value = true
}

async function parseReply(response: Response): Promise<ActionReply> {
  const reply = (await response.json()) as ActionReply
  if (!reply.ok) {
    throw new Error(reply.message || '操作未生效')
  }
  return reply
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const reply = await parseReply(response)
    noticeMessage.value = reply.message
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '判定规则登记失败'
  }
}

async function runAction(action: string, row: Row) {
  if (action === '修订规则') {
    reviseForm.value = {
      "检出限": String(row["检出限"] ?? ''),
      "限量值": String(row["限量值"] ?? ''),
      "单位": String(row["单位"] ?? ''),
    }
    reviseRow.value = row
    return
  }
  await postAction(Number(row.id), { action })
}

async function submitRevise() {
  if (!reviseRow.value) return
  const entryId = Number(reviseRow.value.id)
  reviseRow.value = null
  await postAction(entryId, { action: '修订规则', ...reviseForm.value })
}

async function postAction(entryId: number, values: Record<string, string>) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const reply = await parseReply(response)
    noticeMessage.value = reply.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '判定规则操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const payload = await fetchJson<Page<Row>>(`${ENDPOINT}?${query}`)
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await refreshStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '判定规则列表读取失败'
  }
}

async function refreshStats() {
  const payload = await fetchJson<Page<Row>>(`${ENDPOINT}?size=200`)
  const all = payload.items ?? []
  const active = all.filter((row) => row["规则状态"] === "现行有效")
  stats.value = [
    { label: "现行有效规则", value: active.length },
    { label: "已停用版本", value: all.length - active.length },
    { label: "覆盖检测项目", value: new Set(active.map((row) => row["检测项目"])).size },
  ]
}

onMounted(reload)
</script>
