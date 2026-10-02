import request from './request'

/** 上传数据文件（CSV / XLSX）。 */
export function uploadDataset(projectId, file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`/projects/${projectId}/datasets`, form)
}

/** 当前项目的数据文件列表。 */
export function listDatasets(projectId) {
  return request.get(`/projects/${projectId}/datasets`)
}

/** 预览：表头 + 前若干行。 */
export function previewDataset(projectId, filename, limit = 5) {
  return request.get(`/projects/${projectId}/datasets/${encodeURIComponent(filename)}/preview`, {
    params: { limit },
  })
}

/** 删除数据文件。 */
export function deleteDataset(projectId, filename) {
  return request.delete(`/projects/${projectId}/datasets/${encodeURIComponent(filename)}`)
}
