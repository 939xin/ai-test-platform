import request from './request'

/** 某个项目下的环境列表。 */
export function listEnvironments(projectId) {
  return request.get(`/projects/${projectId}/environments`)
}

/** 在项目下新建环境。 */
export function createEnvironment(projectId, data) {
  return request.post(`/projects/${projectId}/environments`, data)
}

/** 更新环境。 */
export function updateEnvironment(envId, data) {
  return request.put(`/environments/${envId}`, data)
}

/** 删除环境。 */
export function deleteEnvironment(envId) {
  return request.delete(`/environments/${envId}`)
}
