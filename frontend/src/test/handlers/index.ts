import { authHandlers } from './auth'

/** 全局基础 handlers：起服务/认证兜底；领域测试用 server.use 覆盖具体响应。 */
export const handlers = [...authHandlers]