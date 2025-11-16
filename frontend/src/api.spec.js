import { describe, it, expect } from 'vitest'
import config from './config'

describe('API Module', () => {
  it('should have API configuration', () => {
    expect(config.api).toBeDefined()
    expect(config.api.baseURL).toBeDefined()
    // Note: Authentication now uses httpOnly cookies, not API keys in config
  })

  it('should export config object', () => {
    expect(config).toBeDefined()
    expect(typeof config).toBe('object')
  })
})
