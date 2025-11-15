import { describe, it, expect } from 'vitest'
import router from './router'

describe('Router', () => {
  it('should be defined', () => {
    expect(router).toBeDefined()
  })

  it('should have all required routes', () => {
    const routes = router.getRoutes()
    const routeNames = routes.map(r => r.name)

    expect(routeNames).toContain('Dashboard')
    expect(routeNames).toContain('Runners')
    expect(routeNames).toContain('Challenges')
    expect(routeNames).toContain('Logs')
    expect(routeNames).toContain('PublicDashboard')
  })

  it('should have correct route paths', () => {
    const routes = router.getRoutes()

    const dashboard = routes.find(r => r.name === 'Dashboard')
    expect(dashboard.path).toBe('/')

    const runners = routes.find(r => r.name === 'Runners')
    expect(runners.path).toBe('/runners')

    const challenges = routes.find(r => r.name === 'Challenges')
    expect(challenges.path).toBe('/challenges')

    const logs = routes.find(r => r.name === 'Logs')
    expect(logs.path).toBe('/logs')

    const publicDashboard = routes.find(r => r.name === 'PublicDashboard')
    expect(publicDashboard.path).toBe('/public')
  })

  it('should use history mode', () => {
    expect(router.options.history).toBeDefined()
  })
})
