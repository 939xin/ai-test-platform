import request from './request'

/**
 * Web 测试环境探测。
 * 返回 { available, browsers, cache_dir, error, actions, locators }：
 * 前四项判断浏览器能不能用，actions / locators 是步骤编排器渲染下拉用的枚举
 * （定义在后端 services/web_executor.py，前端不另写一份）。
 */
export function getWebStatus() {
  return request.get('/web/status')
}
