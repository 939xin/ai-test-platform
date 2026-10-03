import request from './request'

/** 后端健康检查（同时探活数据库）。登录前就要用，后端对它不校验 token。 */
export function fetchHealth() {
  return request.get('/health')
}
