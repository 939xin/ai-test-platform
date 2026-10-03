import axios from 'axios'
import { ElMessage } from 'element-plus'

import { clearSession, getToken } from './session'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截：带上 JWT
request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * FastAPI 的 detail 有三种形态，统一压成一句可读文案：
 * - 字符串：业务异常自己抛的（如「缺陷不存在」）
 * - 数组：422 参数校验，每项形如 { loc, msg }
 * - 对象：需要带额外数据时（如 409 冲突带已有缺陷 id，正文里是 { message, defect_id }）
 */
function detailToMessage(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || '').filter(Boolean).join('；')
  }
  return detail.message || ''
}

// 登录接口返回的 401 意思是「密码错」，不是「会话过期」，不能走下面的失效处理，
// 否则会在登录页上弹一句莫名其妙的「登录状态已失效」
const LOGIN_URL = '/auth/login'

// 会话过期时页面上往往有好几个请求同时在飞，会连着回来一串 401。
// 这个标记保证只提示一次、只跳一次。
let expiredHandled = false

function handleExpired() {
  clearSession()
  if (expiredHandled) return
  expiredHandled = true
  ElMessage.warning('登录状态已失效，请重新登录')
  // 整页跳转而不是 router.push：既避开「request.js 引 router、router 引组件、
  // 组件又引 api」的循环引用，也顺带清掉各页面残留的内存状态。
  // 登录成功后会整页刷新，这个标记自然复位。
  if (!window.location.pathname.startsWith('/login')) {
    const back = encodeURIComponent(window.location.pathname + window.location.search)
    // 稍微等一下再跳：ElMessage 是挂在当前页面上的，立刻跳会让页面直接卸载，
    // 那句提示根本来不及渲染，用户落到登录页只会一脸茫然。
    setTimeout(() => {
      window.location.href = `/login?redirect=${back}`
    }, 800)
  }
}

// 响应拦截：统一解包 data + 统一报错
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const url = error.config?.url || ''

    if (status === 401 && !url.includes(LOGIN_URL)) {
      handleExpired()
      return Promise.reject(error)
    }

    const message = detailToMessage(error.response?.data?.detail)
      || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
