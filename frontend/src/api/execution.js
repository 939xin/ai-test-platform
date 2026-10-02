import request from './request'

/** 执行单条用例，data 形如 { env_id, timeout }。 */
export function runCase(caseId, data = {}) {
  return request.post(`/cases/${caseId}/run`, data)
}

/** 按数据文件逐行执行用例，返回 {total, passed, failed, rows}。 */
export function runCaseDataDriven(caseId, data = {}) {
  return request.post(`/cases/${caseId}/run-data-driven`, data)
}

/** 执行历史，支持 { project_id, case_id, limit }。 */
export function listExecutions(params = {}) {
  return request.get('/executions', { params })
}

/** 执行详情。 */
export function getExecution(executionId) {
  return request.get(`/executions/${executionId}`)
}
