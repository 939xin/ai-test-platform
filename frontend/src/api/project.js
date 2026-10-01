import request from './request'

/** 项目列表。 */
export function listProjects() {
  return request.get('/projects')
}

/** 新建项目。 */
export function createProject(data) {
  return request.post('/projects', data)
}

/** 更新项目。 */
export function updateProject(id, data) {
  return request.put(`/projects/${id}`, data)
}

/** 删除项目。 */
export function deleteProject(id) {
  return request.delete(`/projects/${id}`)
}
