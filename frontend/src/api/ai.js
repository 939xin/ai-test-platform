import request from './request'

/**
 * AI 相关接口。
 *
 * 两个接口都要单独放宽 axios 超时：后端调 DeepSeek 的超时是 60 秒，还有一次重试，
 * 默认的 30 秒会让前端先断开 —— 用户看到「timeout of 30000ms exceeded」，
 * 以为请求根本没发出去，其实后端还在跑。这里给到 180 秒留足余量。
 */
const AI_TIMEOUT = 180000

/** 根据接口文档生成用例，返回 { task_id, cases, message }。 */
export function generateCases(data) {
  return request.post('/ai/generate-cases', data, { timeout: AI_TIMEOUT })
}

/** 分析一次失败执行，返回 { task_id, possible_causes, troubleshooting_steps, fix_suggestion }。 */
export function analyzeFailure(data) {
  return request.post('/ai/analyze-failure', data, { timeout: AI_TIMEOUT })
}
