import request from './request'

/**
 * Web 登录态：查看 / 清除。
 *
 * 登录态的**写入不在这里** —— 那是「登录用例」执行成功时的副产品，
 * 由后端在执行链路里自动落库。前端只需要能看一眼、能清掉重来。
 *
 * 没有登录态时后端返回 null（不是 404）：「新项目还没登录过」是一种正常状态。
 */
export function getWebSession(projectId) {
  return request.get(`/projects/${projectId}/web-session`)
}

/** 返回 { deleted }：清掉了几个登录态快照 */
export function clearWebSession(projectId) {
  return request.delete(`/projects/${projectId}/web-session`)
}
