import request from './request'

/** 后端健康检查（同时探活数据库）。 */
export function fetchHealth() {
  return request.get('/health')
}

/** 登录，返回 { access_token, token_type, username }。 */
export function login(username, password) {
  return request.post('/auth/login', { username, password })
}
