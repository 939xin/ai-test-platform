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

/**
 * 执行历史，支持 { project_id, case_id, status, limit, offset }。
 * 返回 `{ items, total }` —— total 是筛选后的全部条数，不是本页条数。
 */
export function listExecutions(params = {}) {
  return request.get('/executions', { params })
}

/**
 * 执行统计，支持 { project_id, case_id, status }，返回 { total, passed, failed }。
 *
 * 统计的是**全部**记录，与分页无关。执行中心的统计卡必须走这里，
 * 不能拿列表当前页去 reduce —— 分页之后那样会变成「翻一页数字就变」。
 * failed 是 fail + error 的合计，与那张卡的口径一致。
 */
export function getExecutionStats(params = {}) {
  return request.get('/executions/stats', { params })
}

/** 执行详情。 */
export function getExecution(executionId) {
  return request.get(`/executions/${executionId}`)
}
