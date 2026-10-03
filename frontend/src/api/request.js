import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截：带上 JWT
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
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

// 响应拦截：统一解包 data + 统一报错
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = detailToMessage(error.response?.data?.detail)
      || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
