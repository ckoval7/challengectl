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
    expect(routeNames).toContain('ChallengeConfig')
    expect(routeNames).toContain('Logs')
    expect(routeNames).toContain('PublicDashboard')
  })

  it('should have correct route paths', () => {
    const routes = router.getRoutes()

    const dashboard = routes.find(r => r.name === 'Dashboard')
    expect(dashboard.path).toBe('/admin')

    const runners = routes.find(r => r.name === 'Runners')
    expect(runners.path).toBe('/runners')

    const challengeConfig = routes.find(r => r.name === 'ChallengeConfig')
    expect(challengeConfig.path).toBe('/challenge-config')

    const logs = routes.find(r => r.name === 'Logs')
    expect(logs.path).toBe('/logs')

    const publicDashboard = routes.find(r => r.name === 'PublicDashboard')
    expect(publicDashboard.path).toBe('/public')
  })

  it('should redirect /challenges to /challenge-config', () => {
    const routes = router.getRoutes()
    const challengesRedirect = routes.find(r => r.path === '/challenges')

    expect(challengesRedirect).toBeDefined()
    expect(challengesRedirect.redirect).toBe('/challenge-config')
  })

  it('should use history mode', () => {
    expect(router.options.history).toBeDefined()
  })
})
