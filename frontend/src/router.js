import { createRouter, createWebHistory } from 'vue-router'
import { checkAuth } from './auth'
import Dashboard from './views/Dashboard.vue'
import Runners from './views/Runners.vue'
import Challenges from './views/Challenges.vue'
import Logs from './views/Logs.vue'
import Users from './views/Users.vue'
import PublicDashboard from './views/PublicDashboard.vue'
import Login from './views/Login.vue'
import ChangePassword from './views/ChangePassword.vue'
import InitialSetup from './views/InitialSetup.vue'

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
    meta: { requiresAuth: true }
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: ChangePassword,
    meta: { requiresAuth: true }
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
    name: 'Challenges',
    component: Challenges,
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
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  if (requiresAuth && !checkAuth()) {
    // Redirect to login if trying to access protected route
    next('/login')
  } else if (to.path === '/login' && checkAuth()) {
    // Redirect to admin dashboard if already logged in
    next('/admin')
  } else {
    next()
  }
})

export default router
