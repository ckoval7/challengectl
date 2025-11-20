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
        manualChunks: {
          // Separate Element Plus into its own chunk (largest dependency)
          'element-plus': ['element-plus'],
          // Vue core libraries
          'vue-vendor': ['vue', 'vue-router'],
          // Other vendor libraries
          'vendor-utils': ['axios', 'socket.io-client', 'qrcode']
        }
      }
    }
  }
})
