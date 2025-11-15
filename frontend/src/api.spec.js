import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import { api } from './api'

// Mock axios
vi.mock('axios')

describe('API Module', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should create axios instance with correct config', () => {
    expect(axios.create).toHaveBeenCalled()
    const createCall = axios.create.mock.calls[0][0]

    // Should have authorization header
    expect(createCall.headers).toBeDefined()
    expect(createCall.headers.Authorization).toMatch(/^Bearer /)
  })

  it('should export api instance', () => {
    expect(api).toBeDefined()
    expect(typeof api).toBe('object')
  })
})
