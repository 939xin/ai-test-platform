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

// 响应拦截：统一解包 data + 统一报错
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail
    const message = detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
