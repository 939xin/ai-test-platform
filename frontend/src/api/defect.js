import request from './request'

/**
 * 缺陷枚举 —— 必须与后端 schemas/defect.py 的 Literal 取值逐字一致，
 * 改一边要同步改另一边。列表页、筛选器、编辑抽屉都从这里取，不各写一份。
 */
export const SEVERITY_OPTIONS = ['致命', '严重', '一般', '轻微']
export const PRIORITY_OPTIONS = ['P0', 'P1', 'P2', 'P3']
export const DEFECT_STATUS_OPTIONS = ['新建', '处理中', '已修复', '已关闭', '重新打开']

/**
 * 缺陷列表（分页）。params 支持 { status, severity, keyword, limit, offset }，
 * 返回 `{ items, total }` —— total 是筛选后的全部条数，不是本页条数。
 */
export function listDefects(projectId, params = {}) {
  return request.get(`/projects/${projectId}/defects`, { params })
}

/** 手工新建缺陷。 */
export function createDefect(projectId, data) {
  return request.post(`/projects/${projectId}/defects`, data)
}

/** 缺陷详情（带关联用例名）。 */
export function getDefect(defectId) {
  return request.get(`/defects/${defectId}`)
}

/** 更新缺陷，含状态流转。 */
export function updateDefect(defectId, data) {
  return request.put(`/defects/${defectId}`, data)
}

/** 删除缺陷。 */
export function deleteDefect(defectId) {
  return request.delete(`/defects/${defectId}`)
}

/**
 * 从一条失败 / 错误的执行记录一键提缺陷。
 *
 * 同一条执行已提过时后端返回 409，detail 形如
 * `{ message, defect_id }`，调用方据此跳转到已有缺陷。
 */
export function createDefectFromExecution(executionId, data = {}) {
  return request.post(`/executions/${executionId}/defect`, data)
}
