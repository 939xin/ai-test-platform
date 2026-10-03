import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/components/AppLayout.vue'
import { getToken } from '@/api/session'

// 用例按类型拆成两条独立线路：接口测试 / UI 测试，各有自己的列表与全屏编辑页。
// 编辑页复用同一个组件（views/CaseEditor.vue），由 meta.caseType 决定渲染哪半部分 ——
// 免得把接口与 Web 的保存逻辑各抄一份，日后改一处漏一处。
//
// 注意：这里的 import() 必须写成字面量，Vite 才能静态分析打包。
// 用 `import(type === 'api' ? 'A' : 'B')` 这种计算路径会在运行时报
// "Failed to resolve module specifier"。
const routes = [
  // 登录页在 AppLayout 之外 —— 没登录的人不该看到侧栏菜单
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/projects',
    children: [
      { path: 'projects', name: 'projects', component: () => import('@/views/ProjectList.vue'), meta: { title: '项目管理' } },

      // 旧的合并列表页，保留重定向避免旧链接 404
      { path: 'cases', redirect: '/cases/api' },
      { path: 'cases/api', name: 'api-cases', component: () => import('@/views/ApiCaseList.vue'), meta: { title: '接口测试' } },
      { path: 'cases/api/new', name: 'api-case-new', component: () => import('@/views/CaseEditor.vue'), meta: { title: '新建用例', parent: '接口测试', caseType: 'api' } },
      { path: 'cases/api/:id(\\d+)', name: 'api-case-edit', component: () => import('@/views/CaseEditor.vue'), meta: { title: '编辑用例', parent: '接口测试', caseType: 'api' } },
      { path: 'cases/web', name: 'web-cases', component: () => import('@/views/WebCaseList.vue'), meta: { title: 'UI 测试' } },
      { path: 'cases/web/new', name: 'web-case-new', component: () => import('@/views/CaseEditor.vue'), meta: { title: '新建用例', parent: 'UI 测试', caseType: 'web' } },
      { path: 'cases/web/:id(\\d+)', name: 'web-case-edit', component: () => import('@/views/CaseEditor.vue'), meta: { title: '编辑用例', parent: 'UI 测试', caseType: 'web' } },

      { path: 'scenarios', name: 'scenarios', component: () => import('@/views/ScenarioList.vue'), meta: { title: '场景测试' } },
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

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/**
 * 登录守卫，两个方向都要管：
 * - 没 token 进受保护页面 → 踢回登录页，并把原地址记在 redirect 里，登录后回原位
 * - 已有 token 还去登录页 → 直接送进项目页，免得登录后点后退又回到登录页
 *
 * 这里只看「有没有 token」，不判它过没过期 —— token 过期由后端 401 触发，
 * request.js 会清掉登录态并跳回来，前端不重复解析 JWT。
 */
router.beforeEach((to) => {
  const authed = Boolean(getToken())

  if (!authed && !to.meta.public) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  }
  if (authed && to.name === 'login') {
    return { path: '/projects' }
  }
  return true
})

export default router
