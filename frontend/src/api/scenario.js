import request from './request'

/** 场景列表。 */
export function listScenarios(projectId) {
  return request.get(`/projects/${projectId}/scenarios`)
}

/** 在项目下新建场景。 */
export function createScenario(projectId, data) {
  return request.post(`/projects/${projectId}/scenarios`, data)
}

/** 场景详情（含步骤）。 */
export function getScenario(scenarioId) {
  return request.get(`/scenarios/${scenarioId}`)
}

/** 更新场景；传 steps 会整体替换编排。 */
export function updateScenario(scenarioId, data) {
  return request.put(`/scenarios/${scenarioId}`, data)
}

/** 删除场景。 */
export function deleteScenario(scenarioId) {
  return request.delete(`/scenarios/${scenarioId}`)
}

/** 执行场景，data 形如 { env_id, timeout }。 */
export function runScenario(scenarioId, data = {}) {
  return request.post(`/scenarios/${scenarioId}/run`, data)
}
