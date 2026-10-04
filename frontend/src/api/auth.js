import request from './request'

/** 登录，返回 { access_token, token_type, username }。 */
export function login(username, password) {
  return request.post('/auth/login', { username, password })
}

/**
 * 修改当前登录用户的密码，成功返回 204（无响应体）。
 *
 * 要旧密码是为了挡住「token 被人捡走就能直接改密码」。
 * 后端刻意不吊销已签发的 token —— 改完密码当前的登录态仍然有效，
 * 不用重新登录（旧 token 到期自然失效）。
 */
export function changePassword(oldPassword, newPassword) {
  return request.post('/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
