import request from './request'

/** 执行单条用例，data 形如 { env_id, timeout }。 */
export function runCase(caseId, data = {}) {
  return request.post(`/cases/${caseId}/run`, data)
}

/** 按数据文件逐行执行用例，返回 {total, passed, failed, rows}。 */
export function runCaseDataDriven(caseId, data = {}) {
  return request.post(`/cases/${caseId}/run-data-driven`, data)
}

/**
 * 执行单条 Web UI 用例，data 形如 { env_id, browser, headless, timeout }。
 *
 * 单独放宽 axios 超时：起浏览器、等页面渲染、首次还要下驱动，远不止默认的 30 秒。
 * 这里比后端整条用例的上限（1800 秒）再多一点缓冲，避免前端先断开连接。
 */
export function runWebCase(caseId, data = {}) {
  return request.post(`/cases/${caseId}/run-web`, data, { timeout: 1900000 })
}

/** 执行历史，支持 { project_id, case_id, limit }。 */
export function listExecutions(params = {}) {
  return request.get('/executions', { params })
}

/** 执行详情。 */
export function getExecution(executionId) {
  return request.get(`/executions/${executionId}`)
}
