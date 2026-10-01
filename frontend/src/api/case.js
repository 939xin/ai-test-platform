import request from './request'

/** 用例列表，支持 { type, priority, keyword } 筛选。 */
export function listCases(projectId, params = {}) {
  return request.get(`/projects/${projectId}/cases`, { params })
}

/** 在项目下新建用例。 */
export function createCase(projectId, data) {
  return request.post(`/projects/${projectId}/cases`, data)
}

/** 用例详情。 */
export function getCase(caseId) {
  return request.get(`/cases/${caseId}`)
}

/** 更新用例。 */
export function updateCase(caseId, data) {
  return request.put(`/cases/${caseId}`, data)
}

/** 删除用例。 */
export function deleteCase(caseId) {
  return request.delete(`/cases/${caseId}`)
}
