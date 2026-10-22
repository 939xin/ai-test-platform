/**
 * 长任务接口的超时集中在这里，别在各文件里散落写数字。
 *
 * 全局默认 30 秒（见 request.js）是给普通 CRUD 用的：
 * 一次请求只读/写一行数据，超过 30 秒基本就是真挂了。
 * 但「一次请求触发多步执行」的接口完全是另一回事 —— 用默认值会在 30 秒时
 * 被前端单方面掐断，而后端还在继续跑，用户会在执行中心看到一条与自己
 * 刚才操作对不上的记录。凡是这类接口，**必须显式传 timeout**。
 */

// 后端单次请求上限 120s（api_executor.MAX_TIMEOUT），这里留一倍余量
export const API_TIMEOUT = 240000

// 一条 Web 用例后端最多 1800s（RunCaseDialog 可配），再留余量
export const LONG_TASK_TIMEOUT = 1900000

// AI：后端调 DeepSeek 超时 60s，且会对暂时性故障重试 1 次
export const AI_TIMEOUT = 180000
