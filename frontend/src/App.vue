<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">实验室样品检测管理平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向第三方检测实验室样品接收、任务分配、检测分析、结果复核、报告签发与标物管理的检测业务管理后台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "样品登记", path: "/sample" }, { label: "委托合同", path: "/contract" }, { label: "检测任务", path: "/task" }, { label: "检测方法", path: "/method" }, { label: "仪器设备", path: "/instrument" }, { label: "标准物质", path: "/standard" }, { label: "检测结果", path: "/result" }, { label: "判定规则", path: "/judge-rule" }, { label: "检测报告", path: "/report" }, { label: "分包检测", path: "/boundary" }, { label: "不符合项", path: "/abnormal" }, { label: "环境监控", path: "/envmonitor" }, { label: "盲样考核", path: "/blind" }, { label: "能力验证", path: "/ability" }, { label: "中间液配制", path: "/intermediate" }, { label: "内审检查", path: "/audit" }, { label: "认证认可", path: "/certification" }, { label: "质控样", path: "/quality" }, { label: "试剂管理", path: "/reagent2" }, { label: "实验废液", path: "/waste" }, { label: "客户反馈", path: "/opinion" }]
</script>
