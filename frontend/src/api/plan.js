import request from './request'

/** 计划列表。 */
export function listPlans(projectId) {
  return request.get(`/projects/${projectId}/plans`)
}

/** 在项目下新建计划。 */
export function createPlan(projectId, data) {
  return request.post(`/projects/${projectId}/plans`, data)
}

/** 计划详情（含用例清单）。 */
export function getPlan(planId) {
  return request.get(`/plans/${planId}`)
}

/** 更新计划；传 cases 会整体替换用例清单。 */
export function updatePlan(planId, data) {
  return request.put(`/plans/${planId}`, data)
}

/** 删除计划。 */
export function deletePlan(planId) {
  return request.delete(`/plans/${planId}`)
}

/**
 * 执行计划，data 形如 { env_id, timeout, browser, headless, web_timeout }。
 *
 * 计划里可能混着 Web 用例（一条 3～10 秒），整批远超默认的 30 秒，
 * 所以单独放宽 axios 超时，与 runWebCase 同一量级。
 */
export function runPlan(planId, data = {}) {
  return request.post(`/plans/${planId}/run`, data, { timeout: 1900000 })
}
