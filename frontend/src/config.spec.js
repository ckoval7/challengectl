import { describe, it, expect } from 'vitest'
import config from './config'

describe('Config Module', () => {
  it('should have api configuration', () => {
    expect(config.api).toBeDefined()
    expect(config.api.baseURL).toBeDefined()
    // Note: Authentication now uses httpOnly cookies, not API keys
  })

  it('should have websocket configuration', () => {
    expect(config.websocket).toBeDefined()
    expect(config.websocket.url).toBeDefined()
  })

  it('should have ui configuration', () => {
    expect(config.ui).toBeDefined()
    expect(config.ui.dashboardRefreshInterval).toBeDefined()
    expect(config.ui.runnersRefreshInterval).toBeDefined()
    expect(config.ui.challengesRefreshInterval).toBeDefined()
    expect(config.ui.maxLogEntries).toBeDefined()
  })

  it('should have reasonable default values', () => {
    // Refresh intervals should be in milliseconds (reasonable ranges)
    expect(config.ui.dashboardRefreshInterval).toBeGreaterThan(1000)
    expect(config.ui.dashboardRefreshInterval).toBeLessThan(120000)

    expect(config.ui.runnersRefreshInterval).toBeGreaterThan(1000)
    expect(config.ui.runnersRefreshInterval).toBeLessThan(120000)

    // Max log entries should be reasonable
    expect(config.ui.maxLogEntries).toBeGreaterThan(100)
    expect(config.ui.maxLogEntries).toBeLessThan(10000)
  })
})
