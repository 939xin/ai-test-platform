import request from './request'

/** 按执行记录生成测试报告，data 形如 { execution_ids: [1,2], test_type: 'api' }。 */
export function createReport(projectId, data) {
  return request.post(`/projects/${projectId}/reports`, data)
}

/**
 * 已生成的报告列表，支持 { limit, offset }，返回 `{ items, total }`。
 *
 * 数据来自磁盘上的 HTML 文件而不是数据库，所以每项的标识是 filename（没有 id）。
 */
export function listReports(params = {}) {
  return request.get('/reports', { params })
}

/** 报告的访问地址 —— 后端直接返回 HTML，用新标签页打开（走 vite 的 /api 代理）。 */
export function reportUrl(filename) {
  return `/api/reports/${encodeURIComponent(filename)}`
}
