/**
 * 登录态存取 —— 只读写 localStorage，不依赖任何其他模块。
 *
 * 单独拆一个文件是为了避开循环依赖：request.js（401 时要清登录态）和
 * auth.js（登录成功要写登录态）都需要它，而 request.js 不能反过来 import
 * auth.js —— 那就成了 auth ↔ request 的环，axios 实例会在初始化时拿到 undefined。
 *
 * 以后要加「记住我」「多账号」之类，改这里一处即可。
 */
const TOKEN_KEY = 'token'
const USERNAME_KEY = 'username'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function getUsername() {
  return localStorage.getItem(USERNAME_KEY) || ''
}

export function saveSession(token, username) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USERNAME_KEY, username || '')
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USERNAME_KEY)
}
