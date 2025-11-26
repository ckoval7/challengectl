import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable for detecting screen size breakpoints
 * Returns reactive refs for mobile, tablet, and desktop detection
 *
 * Breakpoints:
 * - Mobile: < 768px
 * - Tablet: 768px - 1024px
 * - Desktop: > 1024px
 */
export function useBreakpoint() {
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(false)
  const windowWidth = ref(0)

  const checkBreakpoint = () => {
    windowWidth.value = window.innerWidth
    isMobile.value = window.innerWidth < 768
    isTablet.value = window.innerWidth >= 768 && window.innerWidth <= 1024
    isDesktop.value = window.innerWidth > 1024
  }

  onMounted(() => {
    checkBreakpoint()
    window.addEventListener('resize', checkBreakpoint)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', checkBreakpoint)
  })

  return {
    isMobile,
    isTablet,
    isDesktop,
    windowWidth
  }
}
