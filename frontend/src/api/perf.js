import request from './request'

/**
 * 压测任务列表，支持 { keyword, limit, offset }，返回 `{ items, total }`。
 * total 是全部条数，不是本页条数。
 */
export function listPerfTasks(projectId, params = {}) {
  return request.get(`/projects/${projectId}/perf-tasks`, { params })
}

/** 在项目下新建压测任务。 */
export function createPerfTask(projectId, data) {
  return request.post(`/projects/${projectId}/perf-tasks`, data)
}

/** 任务详情。 */
export function getPerfTask(taskId) {
  return request.get(`/perf-tasks/${taskId}`)
}

/** 更新任务。 */
export function updatePerfTask(taskId, data) {
  return request.put(`/perf-tasks/${taskId}`, data)
}

/** 删除任务；任务有运行中的压测时后端返回 409。 */
export function deletePerfTask(taskId) {
  return request.delete(`/perf-tasks/${taskId}`)
}

/**
 * 启动压测。后端立即返回 202 { run_id }，真正的压测在后台线程里跑，
 * 进度靠 getPerfRunProgress 轮询。**不要**在这里放大 axios 超时。
 */
export function runPerfTask(taskId, data = {}) {
  return request.post(`/perf-tasks/${taskId}/run`, data)
}

/** 运行记录分页，支持 { project_id, task_id, status, limit, offset }。 */
export function listPerfRuns(params = {}) {
  return request.get('/perf-runs', { params })
}

/**
 * 两次运行对比。left 传较早、right 传较新 —— 后端按 (right-left)/left 算 delta，
 * 方向反了符号与染色会全错，所以由调用方显式按 id 排好。
 */
export function comparePerfRuns(leftId, rightId) {
  return request.get('/perf-runs/compare', { params: { left: leftId, right: rightId } })
}

/** 运行详情（含完整 metrics_json）。 */
export function getPerfRun(runId) {
  return request.get(`/perf-runs/${runId}`)
}

/** 实时进度；终态时后端返回最终摘要。 */
export function getPerfRunProgress(runId) {
  return request.get(`/perf-runs/${runId}/progress`)
}

/** 停止压测，幂等。 */
export function stopPerfRun(runId) {
  return request.post(`/perf-runs/${runId}/stop`)
}

/** 删除运行记录（仅终态）。 */
export function deletePerfRun(runId) {
  return request.delete(`/perf-runs/${runId}`)
}

/** 本机压测上限，编辑器与运行弹窗都用它，不在前端另写一份数字。 */
export function getPerfLimits() {
  return request.get('/perf-limits')
}

/** 压测运行的状态是否仍活跃（用于决定要不要继续轮询）。 */
export const ACTIVE_PERF_STATUSES = ['queued', 'running', 'stopping']
