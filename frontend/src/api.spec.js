import { describe, it, expect } from 'vitest'
import config from './config'

describe('API Module', () => {
  it('should have API configuration', () => {
    expect(config.api).toBeDefined()
    expect(config.api.baseURL).toBeDefined()
    expect(config.api.apiKey).toBeDefined()
  })

  it('should export config object', () => {
    expect(config).toBeDefined()
    expect(typeof config).toBe('object')
  })
})
