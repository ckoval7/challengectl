import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8443',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Separate node_modules into vendor chunk
          if (id.includes('node_modules')) {
            // Keep Element Plus separate as it's the largest dependency
            if (id.includes('element-plus')) {
              return 'element-plus'
            }
            // Group all other vendor dependencies together
            return 'vendor'
          }
        }
      }
    }
  }
})
