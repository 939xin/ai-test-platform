import request from './request'

/**
 * 用例列表，支持 { type, priority, keyword, tag, enabled, limit, offset } 筛选 + 分页。
 * 返回 `{ items, total }` —— total 是筛选后的全部条数，不是本页条数。
 *
 * `tag` 传数组时按「或」匹配。这里必须指定 `indexes: null`：
 * axios 默认把数组序列化成 `tag[]=a&tag[]=b`，FastAPI 只认重复的同名参数 `tag=a&tag=b`。
 *
 * ⚠️ 后端默认一页 20 条。当「下拉数据源」用的调用点（计划 / 场景编辑器挑用例）
 * 得显式传一个大 limit，否则选择器只会列出头 20 条。
 */
export function listCases(projectId, params = {}) {
  return request.get(`/projects/${projectId}/cases`, {
    params,
    paramsSerializer: { indexes: null },
  })
}

/** 项目内出现过的标签，裸数组（筛选器的下拉数据源）。 */
export function listCaseTags(projectId, type) {
  return request.get(`/projects/${projectId}/case-tags`, { params: { type } })
}

/** 批量启用 / 停用 / 删除。跨项目会被后端拒绝（400），不做部分成功。 */
export function batchCases(payload) {
  return request.post('/cases/batch', payload)
}

/** 克隆用例：副本强制停用，JSON 字段深拷贝。 */
export function cloneCase(caseId) {
  return request.post(`/cases/${caseId}/clone`)
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
