import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/components/AppLayout.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    redirect: '/projects',
    children: [
      { path: 'projects', name: 'projects', component: () => import('@/views/ProjectList.vue'), meta: { title: '项目管理' } },
      { path: 'cases', name: 'cases', component: () => import('@/views/CaseList.vue'), meta: { title: '用例管理' } },
      { path: 'plans', name: 'plans', component: () => import('@/views/PlanList.vue'), meta: { title: '测试计划' } },
      { path: 'executions', name: 'executions', component: () => import('@/views/ExecutionCenter.vue'), meta: { title: '执行中心' } },
      { path: 'reports', name: 'reports', component: () => import('@/views/ReportList.vue'), meta: { title: '测试报告' } },
      { path: 'defects', name: 'defects', component: () => import('@/views/DefectList.vue'), meta: { title: '缺陷管理' } },
      { path: 'environments', name: 'environments', component: () => import('@/views/EnvironmentList.vue'), meta: { title: '环境变量' } },
      { path: 'ai', name: 'ai', component: () => import('@/views/AIAssistant.vue'), meta: { title: 'AI 助手' } },
      { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '设置' } },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
