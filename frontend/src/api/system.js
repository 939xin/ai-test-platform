import request from './request'

/**
 * 系统信息：版本 / 当前用户 / 数据库 / 各目录 / 浏览器驱动 / AI 配置状态。
 *
 * 一次请求拿全，是因为这些都是「本机当前状态」—— 拆成多个请求再拼，
 * 页面可能显示出互相矛盾的组合（比如数据库刚断，一半卡片说好一半说坏）。
 */
export function getSystemInfo() {
  return request.get('/system/info')
}
