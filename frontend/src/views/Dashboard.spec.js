import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Dashboard from './Dashboard.vue'
import { api } from '../api'

// Mock the API module
vi.mock('../api', () => ({
  api: {
    get: vi.fn()
  }
}))

// Mock websocket
vi.mock('../websocket', () => ({
  websocket: {
    on: vi.fn(),
    off: vi.fn()
  }
}))

describe('Dashboard Component', () => {
  let wrapper

  beforeEach(() => {
    // Mock API response
    api.get.mockResolvedValue({
      data: {
        stats: {
          runners_online: 2,
          runners_total: 3,
          challenges_queued: 5,
          challenges_total: 10,
          total_transmissions: 42,
          transmissions_last_hour: 12,
          success_rate: 95.5
        },
        runners: [
          {
            runner_id: 'runner-1',
            hostname: 'test-host-1',
            status: 'online',
            devices: [{ id: 0, type: 'HackRF' }],
            last_heartbeat: new Date().toISOString()
          }
        ],
        recent_transmissions: [
          {
            challenge_name: 'TEST_CHALLENGE',
            frequency: 146550000,
            status: 'success',
            completed_at: new Date().toISOString()
          }
        ]
      }
    })
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    vi.clearAllMocks()
  })

  it('should render component', () => {
    wrapper = mount(Dashboard)
    expect(wrapper.exists()).toBe(true)
  })

  it('should load dashboard data on mount', async () => {
    wrapper = mount(Dashboard)
    await wrapper.vm.$nextTick()

    expect(api.get).toHaveBeenCalledWith('/dashboard')
  })

  it('should display stats correctly', async () => {
    wrapper = mount(Dashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.stats.runners_online).toBe(2)
    expect(wrapper.vm.stats.challenges_queued).toBe(5)
    expect(wrapper.vm.stats.total_transmissions).toBe(42)
  })

  it('should display runners list', async () => {
    wrapper = mount(Dashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.runners).toHaveLength(1)
    expect(wrapper.vm.runners[0].runner_id).toBe('runner-1')
  })

  it('should display recent transmissions', async () => {
    wrapper = mount(Dashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.recentTransmissions).toHaveLength(1)
    expect(wrapper.vm.recentTransmissions[0].challenge_name).toBe('TEST_CHALLENGE')
  })

  it('should format frequency correctly', () => {
    wrapper = mount(Dashboard)
    const formatFrequency = wrapper.vm.formatFrequency

    expect(formatFrequency(146550000)).toBe('146.550 MHz')
    expect(formatFrequency(433920000)).toBe('433.920 MHz')
  })

  it('should format time correctly', () => {
    wrapper = mount(Dashboard)
    const formatTime = wrapper.vm.formatTime

    const now = new Date()
    const result = formatTime(now.toISOString())

    // Should return a string
    expect(typeof result).toBe('string')
  })
})
