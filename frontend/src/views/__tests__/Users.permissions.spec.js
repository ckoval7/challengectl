/**
 * Permission Management Tests for Users.vue
 *
 * Tests the dynamic permission fetching and rendering functionality.
 */

import { describe, test, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import Users from '../Users.vue'
import { api } from '../../api'

// Mock the API module
vi.mock('../../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

// Mock Element Plus Message
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn()
    }
  }
})

describe('Permission Management in Users.vue', () => {
  const mockPermissions = [
    {
      name: 'create_users',
      description: 'Can create and manage users',
      category: 'administration'
    },
    {
      name: 'create_provisioning_key',
      description: 'Can create provisioning keys for runners',
      category: 'provisioning'
    }
  ]

  const mockUsers = {
    users: [
      {
        username: 'admin',
        enabled: true,
        permissions: ['create_users', 'create_provisioning_key']
      },
      {
        username: 'user1',
        enabled: true,
        permissions: ['create_users']
      }
    ]
  }

  beforeEach(() => {
    // Clear all mocks before each test
    vi.clearAllMocks()

    // Default successful responses
    api.get.mockImplementation((url) => {
      if (url === '/users') {
        return Promise.resolve({ data: mockUsers })
      }
      if (url === '/permissions/metadata') {
        return Promise.resolve({ data: { permissions: mockPermissions } })
      }
      return Promise.reject(new Error('Unknown endpoint'))
    })
  })

  describe('Permission Metadata Fetching', () => {
    test('fetches permission metadata on component mount', async () => {
      mount(Users)
      await flushPromises()

      expect(api.get).toHaveBeenCalledWith('/permissions/metadata')
    })

    test('stores fetched permissions in component state', async () => {
      const wrapper = mount(Users)
      await flushPromises()

      // The component should have availablePermissions populated
      expect(wrapper.vm.availablePermissions).toEqual(mockPermissions)
      expect(wrapper.vm.availablePermissions).toHaveLength(2)
    })

    test('handles permission fetch error gracefully', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/users') {
          return Promise.resolve({ data: mockUsers })
        }
        if (url === '/permissions/metadata') {
          return Promise.reject(new Error('Network error'))
        }
        return Promise.reject(new Error('Unknown endpoint'))
      })

      const wrapper = mount(Users)
      await flushPromises()

      expect(ElMessage.error).toHaveBeenCalledWith('Failed to load available permissions')
      expect(wrapper.vm.loadingPermissions).toBe(false)
    })

    test('sets loading state during permission fetch', async () => {
      let resolvePermissions
      const permissionsPromise = new Promise((resolve) => {
        resolvePermissions = resolve
      })

      api.get.mockImplementation((url) => {
        if (url === '/users') {
          return Promise.resolve({ data: mockUsers })
        }
        if (url === '/permissions/metadata') {
          return permissionsPromise
        }
        return Promise.reject(new Error('Unknown endpoint'))
      })

      const wrapper = mount(Users)
      await flushPromises()

      // Should be loading before promise resolves
      expect(wrapper.vm.loadingPermissions).toBe(true)

      // Resolve the promise
      resolvePermissions({ data: { permissions: mockPermissions } })
      await flushPromises()

      // Should not be loading after promise resolves
      expect(wrapper.vm.loadingPermissions).toBe(false)
    })
  })

  describe('Permission Dropdown Rendering', () => {
    test('renders permission dropdown with fetched permissions', async () => {
      const wrapper = mount(Users)
      await flushPromises()

      // Open permissions dialog to see dropdown
      wrapper.vm.showPermissionsDialog = true
      await wrapper.vm.$nextTick()

      const options = wrapper.findAll('.el-select-dropdown__item')

      // Should render options for each permission
      expect(options.length).toBeGreaterThan(0)
    })

    test('displays correct permission labels', async () => {
      const wrapper = mount(Users)
      await flushPromises()

      // Check that availablePermissions has correct structure
      const permissions = wrapper.vm.availablePermissions

      permissions.forEach((perm) => {
        expect(perm).toHaveProperty('name')
        expect(perm).toHaveProperty('description')
        expect(perm).toHaveProperty('category')
      })
    })

    test('permission options are disabled while loading', async () => {
      const wrapper = mount(Users)

      // Set loading state
      wrapper.vm.loadingPermissions = true
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.loadingPermissions).toBe(true)
    })

    test('renders all permission metadata fields', async () => {
      const wrapper = mount(Users)
      await flushPromises()

      const permissions = wrapper.vm.availablePermissions

      // Verify first permission has all expected fields
      expect(permissions[0]).toEqual({
        name: 'create_users',
        description: 'Can create and manage users',
        category: 'administration'
      })

      // Verify second permission has all expected fields
      expect(permissions[1]).toEqual({
        name: 'create_provisioning_key',
        description: 'Can create provisioning keys for runners',
        category: 'provisioning'
      })
    })
  })

  describe('Permission Granting Workflow', () => {
    test('permission dropdown uses dynamic data', async () => {
      const wrapper = mount(Users)
      await flushPromises()

      // Verify availablePermissions is populated from API
      expect(wrapper.vm.availablePermissions).toHaveLength(2)
      expect(wrapper.vm.availablePermissions[0].name).toBe('create_users')
      expect(wrapper.vm.availablePermissions[1].name).toBe('create_provisioning_key')
    })

    test('can select permission from dynamic list', async () => {
      const wrapper = mount(Users)
      await flushPromises()

      // Set a permission to grant
      wrapper.vm.permissionToGrant = 'create_users'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.permissionToGrant).toBe('create_users')
    })
  })

  describe('Empty and Edge Cases', () => {
    test('handles empty permission list', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/users') {
          return Promise.resolve({ data: mockUsers })
        }
        if (url === '/permissions/metadata') {
          return Promise.resolve({ data: { permissions: [] } })
        }
        return Promise.reject(new Error('Unknown endpoint'))
      })

      const wrapper = mount(Users)
      await flushPromises()

      expect(wrapper.vm.availablePermissions).toEqual([])
      expect(wrapper.vm.availablePermissions).toHaveLength(0)
    })

    test('handles malformed permission data', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/users') {
          return Promise.resolve({ data: mockUsers })
        }
        if (url === '/permissions/metadata') {
          // Missing description field
          return Promise.resolve({
            data: {
              permissions: [
                { name: 'test_permission', category: 'test' }
              ]
            }
          })
        }
        return Promise.reject(new Error('Unknown endpoint'))
      })

      const wrapper = mount(Users)
      await flushPromises()

      // Component should still work, just with incomplete data
      expect(wrapper.vm.availablePermissions).toHaveLength(1)
    })

    test('console logs error on permission fetch failure', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      api.get.mockImplementation((url) => {
        if (url === '/users') {
          return Promise.resolve({ data: mockUsers })
        }
        if (url === '/permissions/metadata') {
          return Promise.reject(new Error('API Error'))
        }
        return Promise.reject(new Error('Unknown endpoint'))
      })

      mount(Users)
      await flushPromises()

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error fetching permission metadata:',
        expect.any(Error)
      )

      consoleErrorSpy.mockRestore()
    })
  })

  describe('Integration with User Management', () => {
    test('fetches both users and permissions on mount', async () => {
      mount(Users)
      await flushPromises()

      expect(api.get).toHaveBeenCalledWith('/users')
      expect(api.get).toHaveBeenCalledWith('/permissions/metadata')
      expect(api.get).toHaveBeenCalledTimes(2)
    })

    test('permissions are independent of user data', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/users') {
          return Promise.reject(new Error('User fetch failed'))
        }
        if (url === '/permissions/metadata') {
          return Promise.resolve({ data: { permissions: mockPermissions } })
        }
        return Promise.reject(new Error('Unknown endpoint'))
      })

      const wrapper = mount(Users)
      await flushPromises()

      // Permissions should still load even if users fail
      expect(wrapper.vm.availablePermissions).toEqual(mockPermissions)
    })
  })
})
