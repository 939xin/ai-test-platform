import request from './request'

/** 登录，返回 { access_token, token_type, username }。 */
export function login(username, password) {
  return request.post('/auth/login', { username, password })
}
