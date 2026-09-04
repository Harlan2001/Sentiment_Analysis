import { setupServer } from 'msw/node'
import { handlers } from './handlers'

/** 测试用 MSW server：拦截 fetch（request()/直接 fetch 都经此） */
export const server = setupServer(...handlers)