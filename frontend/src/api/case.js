import request from './request'

/**
 * 用例列表，支持 { type, priority, keyword, limit, offset } 筛选 + 分页。
 * 返回 `{ items, total }` —— total 是筛选后的全部条数，不是本页条数。
 *
 * ⚠️ 后端默认一页 20 条。当「下拉数据源」用的调用点（计划 / 场景编辑器挑用例）
 * 得显式传一个大 limit，否则选择器只会列出头 20 条。
 */
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
