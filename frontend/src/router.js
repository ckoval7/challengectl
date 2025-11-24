import { createRouter, createWebHistory } from 'vue-router'
import { checkAuth, validateSession, isSessionChecked, isInitialSetupRequired, hasPermission } from './auth'
import { ElMessage } from 'element-plus'

// Lazy load all route components for better code splitting
const Dashboard = () => import('./views/Dashboard.vue')
const Runners = () => import('./views/Runners.vue')
const ChallengeConfig = () => import('./views/ChallengeConfig.vue')
const RecordingHistory = () => import('./views/RecordingHistory.vue')
const Logs = () => import('./views/Logs.vue')
const Users = () => import('./views/Users.vue')
const PublicDashboard = () => import('./views/PublicDashboard.vue')
const Login = () => import('./views/Login.vue')
const ChangePassword = () => import('./views/ChangePassword.vue')
const InitialSetup = () => import('./views/InitialSetup.vue')
const UserSetup = () => import('./views/UserSetup.vue')
const NotFound = () => import('./views/NotFound.vue')

const routes = [
  {
    path: '/',
    redirect: '/public'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/public',
    name: 'PublicDashboard',
    component: PublicDashboard
  },
  {
    path: '/initial-setup',
    name: 'InitialSetup',
    component: InitialSetup,
    meta: { requiresAuth: true, hideLayout: true }
  },
  {
    path: '/user-setup',
    name: 'UserSetup',
    component: UserSetup,
    meta: { requiresAuth: true, hideLayout: true }
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: ChangePassword,
    meta: { requiresAuth: true, hideLayout: true }
  },
  {
    path: '/admin',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/runners',
    name: 'Runners',
    component: Runners,
    meta: { requiresAuth: true }
  },
  {
    path: '/challenges',
    redirect: '/challenge-config'
  },
  {
    path: '/challenge-config',
    name: 'ChallengeConfig',
    component: ChallengeConfig,
    meta: { requiresAuth: true }
  },
  {
    path: '/recordings/:challengeId',
    name: 'RecordingHistory',
    component: RecordingHistory,
    meta: { requiresAuth: true }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: Logs,
    meta: { requiresAuth: true }
  },
  {
    path: '/users',
    name: 'Users',
    component: Users,
    meta: { requiresAuth: true, requiresPermission: 'create_users' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFound
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard for authentication
// Validates session with backend on first navigation or page refresh
router.beforeEach(async (to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  // If already authenticated in memory, fast path
  if (checkAuth()) {
    // Check if initial setup is required
    if (isInitialSetupRequired()) {
      // User must complete initial setup before accessing other routes
      if (to.path !== '/initial-setup' && to.path !== '/login') {
        next('/initial-setup')
        return
      }
    }

    // Check if route requires specific permission
    const requiredPermission = to.meta.requiresPermission
    if (requiredPermission && !hasPermission(requiredPermission)) {
      ElMessage.error('You do not have permission to access this page.')
      next('/admin')
      return
    }

    if (to.path === '/login') {
      // Already logged in, redirect appropriately
      if (isInitialSetupRequired()) {
        next('/initial-setup')
      } else {
        next('/admin')
      }
    } else {
      next()
    }
    return
  }

  // If not authenticated in memory but haven't checked session yet,
  // validate with backend (handles page refresh)
  if (!isSessionChecked()) {
    const isValid = await validateSession()

    if (isValid) {
      // Session is valid, check if initial setup is required
      if (isInitialSetupRequired()) {
        // User must complete initial setup before accessing other routes
        if (to.path !== '/initial-setup' && to.path !== '/login') {
          next('/initial-setup')
          return
        }
      }

      // Check if route requires specific permission
      const requiredPermission = to.meta.requiresPermission
      if (requiredPermission && !hasPermission(requiredPermission)) {
        ElMessage.error('You do not have permission to access this page.')
        next('/admin')
        return
      }

      // Allow navigation
      if (to.path === '/login') {
        if (isInitialSetupRequired()) {
          next('/initial-setup')
        } else {
          next('/admin')
        }
      } else {
        next()
      }
      return
    }
  }

  // Not authenticated and session is invalid
  if (requiresAuth) {
    // Redirect to login if trying to access protected route
    next('/login')
  } else {
    next()
  }
})

export default router
