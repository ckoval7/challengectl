import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PublicDashboard from './PublicDashboard.vue'
import axios from 'axios'

// Mock axios
vi.mock('axios')

describe('PublicDashboard', () => {
  let wrapper

  beforeEach(() => {
    vi.useFakeTimers()
    // Mock successful API response
    axios.get = vi.fn().mockResolvedValue({
      data: {
        challenges: [
          {
            challenge_id: '1',
            name: 'TEST_CHALLENGE_1',
            modulation: 'nbfm',
            transmission_count: 5,
            frequency: 146550000,
            frequency_display: '146.550 MHz',
            last_tx_time: '2025-01-15T10:00:00Z',
            is_active: true
          },
          {
            challenge_id: '2',
            name: 'TEST_CHALLENGE_2',
            modulation: 'cw',
            transmission_count: 3
          }
        ],
        count: 2,
        timestamp: '2025-01-15T12:00:00Z'
      }
    })
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('should render component', () => {
    wrapper = mount(PublicDashboard)
    expect(wrapper.exists()).toBe(true)
  })

  it('should show loading state initially', () => {
    wrapper = mount(PublicDashboard)
    expect(wrapper.find('.loading-container').exists()).toBe(true)
  })

  it('should fetch challenges on mount', async () => {
    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()

    expect(axios.get).toHaveBeenCalledWith('/api/public/challenges')
  })

  it('should display challenges after loading', async () => {
    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.challenges).toHaveLength(2)
    expect(wrapper.vm.loading).toBe(false)
  })

  it('should show error state on API failure', async () => {
    axios.get = vi.fn().mockRejectedValue(new Error('Network error'))

    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.error).toBeTruthy()
    expect(wrapper.vm.loading).toBe(false)
  })

  it('should show empty state when no challenges', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        challenges: [],
        count: 0
      }
    })

    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.challenges).toHaveLength(0)
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('should format time correctly', () => {
    wrapper = mount(PublicDashboard)
    const formatTime = wrapper.vm.formatTime

    // Test null/undefined
    expect(formatTime(null)).toBe('N/A')

    // Test recent time
    const now = new Date()
    expect(formatTime(now.toISOString())).toBe('Just now')

    // Test minutes ago
    const minsAgo = new Date(now.getTime() - 5 * 60 * 1000)
    expect(formatTime(minsAgo.toISOString())).toBe('5m ago')

    // Test hours ago
    const hoursAgo = new Date(now.getTime() - 3 * 60 * 60 * 1000)
    expect(formatTime(hoursAgo.toISOString())).toBe('3h ago')
  })

  it('should set up auto-refresh on mount', async () => {
    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()

    // Fast-forward time
    vi.advanceTimersByTime(30000)

    // Should have called API again
    expect(axios.get).toHaveBeenCalledTimes(2)
  })

  it('should clean up auto-refresh on unmount', async () => {
    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()

    const initialCallCount = axios.get.mock.calls.length

    wrapper.unmount()
    vi.advanceTimersByTime(30000)

    // Should not call API after unmount
    expect(axios.get).toHaveBeenCalledTimes(initialCallCount)
  })

  it('should conditionally show frequency column', async () => {
    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasAnyFrequencyVisible).toBe(true)
  })

  it('should conditionally show last transmission column', async () => {
    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasAnyLastTxVisible).toBe(true)
  })

  it('should conditionally show active status column', async () => {
    wrapper = mount(PublicDashboard)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasAnyActiveStatusVisible).toBe(true)
  })
})
