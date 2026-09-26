<template>
  <section class="page" data-module="result">
    <header class="page-head">
      <div>
        <h2>检测结果管理</h2>
        <p class="page-desc">检测值录入后按判定规则自动比对检出限与评价标准给出结论，判定依据随结果留存，复核人看到的与录入时一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检测结果</button>
        <button class="btn" type="button" @click="exportRows">导出检测结果清单</button>
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
        <input v-model="createForm[field.key]" :list="field.list" :placeholder="field.placeholder" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>结果编号</span>
        <input v-model="keyword" placeholder="按结果编号检索" />
      </label>
      <label class="filter-item">
        <span>结果状态</span>
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
            <span v-if="column === '判定结论'" class="tag" :class="conclusionClass(row[column])">
              {{ row[column] || '未生成' }}
            </span>
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
            <button class="link" type="button" @click="openDetail(row)">判定依据</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无检测结果数据，可先登记检测结果</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检测结果记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <datalist id="rule-items">
      <option v-for="item in ruleItems" :key="item" :value="item" />
    </datalist>
    <datalist id="rule-standards">
      <option v-for="standard in ruleStandards" :key="standard" :value="standard" />
    </datalist>

    <div v-if="entryRow" class="modal-mask" @click.self="entryRow = null">
      <div class="modal-card">
        <h3>录入结果 · {{ entryRow['结果编号'] }}</h3>
        <form class="modal-form" @submit.prevent="submitEntry">
          <label class="filter-item">
            <span>检测值</span>
            <input v-model="entryForm['检测值']" placeholder="数值，或 <0.05、未检出" />
          </label>
          <label class="filter-item">
            <span>评价标准</span>
            <input v-model="entryForm['评价标准']" list="rule-standards" placeholder="选择评价标准" />
          </label>
          <div class="modal-actions">
            <button class="btn primary" type="submit">提交并自动判定</button>
            <button class="btn ghost" type="button" @click="entryRow = null">取消</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal-card">
        <h3>判定依据 · {{ detail['结果编号'] }}</h3>
        <table v-if="snapshotEntries.length" class="kv-table">
          <tbody>
            <tr v-for="[key, value] in snapshotEntries" :key="key">
              <th>{{ key }}</th>
              <td>{{ value ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty-state">{{ detail['判定说明'] || '尚未生成判定结论' }}</p>
        <div v-if="historyList.length" class="history-block">
          <h4>判定历史（重判作废旧依据）</h4>
          <table v-for="(item, index) in historyList" :key="index" class="kv-table">
            <tbody>
              <tr v-for="[key, value] in Object.entries(item)" :key="key">
                <th>{{ key }}</th>
                <td>{{ value ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-actions">
          <button class="btn" type="button" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, any>
type Page<T> = { items: T[]; total: number }
type ActionReply = { ok: boolean; message: string; entry: Row | null }

const ENDPOINT = '/api/result'
const RULE_ENDPOINT = '/api/judgerule'
const columns = ["结果编号", "关联任务", "检测项目", "检测值", "评价标准", "判定结论", "判定说明", "结果状态"]
const actions = ["录入结果", "提交复核", "退回修正", "重新判定"]
const statuses = ["待录入", "待复核", "已复核", "已退回"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: "待复核结果", value: 0 },
  { label: "已复核结果", value: 0 },
  { label: "未生成结论", value: 0 },
])
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')

const showCreate = ref(false)
const createFields = [
  { key: "结果编号", label: "结果编号", placeholder: "如 RESU-1001" },
  { key: "关联任务", label: "关联任务", placeholder: "如 TASK-0001" },
  { key: "检测项目", label: "检测项目", list: "rule-items", placeholder: "选择或输入检测项目" },
  { key: "检测值", label: "检测值", placeholder: "数值，或 <0.05、未检出" },
  { key: "评价标准", label: "评价标准", list: "rule-standards", placeholder: "选择评价标准" },
]
const createForm = ref<Record<string, string>>({})

const rules = ref<Row[]>([])
const ruleItems = computed(() => [...new Set(rules.value.map((rule) => String(rule["检测项目"] ?? "")))].filter(Boolean))
const ruleStandards = computed(() => {
  const item = createForm.value["检测项目"]
  const matched = item ? rules.value.filter((rule) => rule["检测项目"] === item) : rules.value
  return [...new Set(matched.map((rule) => String(rule["评价标准"] ?? "")))].filter(Boolean)
})

const entryRow = ref<Row | null>(null)
const entryForm = ref<Record<string, string>>({})

const detail = ref<Row | null>(null)
const snapshotEntries = computed(() => Object.entries(detail.value?.["判定快照"] ?? {}))
const historyList = computed(() => (detail.value?.["判定历史"] ?? []) as Row[])

function conclusionClass(value: unknown) {
  if (value === "合格") return "pass"
  if (value === "不合格") return "fail"
  if (value === "未检出") return "nd"
  return ""
}

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
    errorMessage.value = error instanceof Error ? error.message : '检测结果登记失败'
  }
}

async function runAction(action: string, row: Row) {
  if (action === '录入结果') {
    entryForm.value = { "检测值": String(row["检测值"] ?? ''), "评价标准": String(row["评价标准"] ?? '') }
    entryRow.value = row
    return
  }
  await postAction(Number(row.id), { action })
}

async function submitEntry() {
  if (!entryRow.value) return
  const entryId = Number(entryRow.value.id)
  entryRow.value = null
  await postAction(entryId, { action: '录入结果', ...entryForm.value })
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
    errorMessage.value = error instanceof Error ? error.message : '检测结果操作失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    detail.value = await fetchJson<Row>(`${ENDPOINT}/${row.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '判定依据读取失败'
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
    errorMessage.value = error instanceof Error ? error.message : '检测结果列表读取失败'
  }
}

async function refreshStats() {
  const payload = await fetchJson<Page<Row>>(`${ENDPOINT}?size=200`)
  const all = payload.items ?? []
  stats.value = [
    { label: "待复核结果", value: all.filter((row) => row.status === "待复核").length },
    { label: "已复核结果", value: all.filter((row) => row.status === "已复核").length },
    { label: "未生成结论", value: all.filter((row) => !row["判定结论"]).length },
  ]
}

async function loadRules() {
  try {
    const query = new URLSearchParams({ status: "现行有效", size: "200" })
    const payload = await fetchJson<Page<Row>>(`${RULE_ENDPOINT}?${query}`)
    rules.value = payload.items ?? []
  } catch {
    rules.value = []
  }
}

onMounted(() => {
  void reload()
  void loadRules()
})
</script>
