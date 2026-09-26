import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Sample = () => import('@/views/sample/index.vue')
const Contract = () => import('@/views/contract/index.vue')
const Task = () => import('@/views/task/index.vue')
const Method = () => import('@/views/method/index.vue')
const Instrument = () => import('@/views/instrument/index.vue')
const Standard = () => import('@/views/standard/index.vue')
const Judgerule = () => import('@/views/judgerule/index.vue')
const Result = () => import('@/views/result/index.vue')
const Report = () => import('@/views/report/index.vue')
const Boundary = () => import('@/views/boundary/index.vue')
const Abnormal = () => import('@/views/abnormal/index.vue')
const Envmonitor = () => import('@/views/envmonitor/index.vue')
const Blind = () => import('@/views/blind/index.vue')
const Ability = () => import('@/views/ability/index.vue')
const Intermediate = () => import('@/views/intermediate/index.vue')
const Audit = () => import('@/views/audit/index.vue')
const Certification = () => import('@/views/certification/index.vue')
const Quality = () => import('@/views/quality/index.vue')
const Reagent2 = () => import('@/views/reagent2/index.vue')
const Waste = () => import('@/views/waste/index.vue')
const Opinion = () => import('@/views/opinion/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/sample', name: 'sample', component: Sample },
    { path: '/contract', name: 'contract', component: Contract },
    { path: '/task', name: 'task', component: Task },
    { path: '/method', name: 'method', component: Method },
    { path: '/instrument', name: 'instrument', component: Instrument },
    { path: '/standard', name: 'standard', component: Standard },
    { path: '/judgerule', name: 'judgerule', component: Judgerule },
    { path: '/result', name: 'result', component: Result },
    { path: '/report', name: 'report', component: Report },
    { path: '/boundary', name: 'boundary', component: Boundary },
    { path: '/abnormal', name: 'abnormal', component: Abnormal },
    { path: '/envmonitor', name: 'envmonitor', component: Envmonitor },
    { path: '/blind', name: 'blind', component: Blind },
    { path: '/ability', name: 'ability', component: Ability },
    { path: '/intermediate', name: 'intermediate', component: Intermediate },
    { path: '/audit', name: 'audit', component: Audit },
    { path: '/certification', name: 'certification', component: Certification },
    { path: '/quality', name: 'quality', component: Quality },
    { path: '/reagent2', name: 'reagent2', component: Reagent2 },
    { path: '/waste', name: 'waste', component: Waste },
    { path: '/opinion', name: 'opinion', component: Opinion },
  ],
})

export default router
