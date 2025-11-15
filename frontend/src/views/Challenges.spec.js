import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Challenges from './Challenges.vue'
import { api } from '../api'

// Mock the API module
vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn()
  }
}))

// Mock websocket
vi.mock('../websocket', () => ({
  websocket: {
    on: vi.fn(),
    off: vi.fn()
  }
}))

describe('Challenges Component', () => {
  let wrapper

  beforeEach(() => {
    // Mock API response
    api.get.mockResolvedValue({
      data: {
        challenges: [
          {
            challenge_id: '1',
            name: 'TEST_CHALLENGE_1',
            config: {
              modulation: 'nbfm',
              frequency: 146550000
            },
            status: 'queued',
            enabled: true,
            transmission_count: 5,
            last_tx_time: new Date().toISOString()
          },
          {
            challenge_id: '2',
            name: 'TEST_CHALLENGE_2',
            config: {
              modulation: 'cw',
              frequency: 146450000
            },
            status: 'assigned',
            enabled: true,
            transmission_count: 3,
            assigned_to: 'runner-1'
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
    wrapper = mount(Challenges)
    expect(wrapper.exists()).toBe(true)
  })

  it('should load challenges on mount', async () => {
    wrapper = mount(Challenges)
    await wrapper.vm.$nextTick()

    expect(api.get).toHaveBeenCalledWith('/challenges')
  })

  it('should display challenges list', async () => {
    wrapper = mount(Challenges)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.challenges).toHaveLength(2)
    expect(wrapper.vm.challenges[0].name).toBe('TEST_CHALLENGE_1')
  })

  it('should format frequency correctly', () => {
    wrapper = mount(Challenges)
    const formatFrequency = wrapper.vm.formatFrequency

    expect(formatFrequency(146550000)).toBe('146.550 MHz')
    expect(formatFrequency(433920000)).toBe('433.920 MHz')
  })
})
