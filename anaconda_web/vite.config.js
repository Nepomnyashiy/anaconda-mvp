import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Проксирование API запросов к бэкенду
    proxy: {
      '/api': {
        target: 'http://anaconda-api:8000',
        changeOrigin: true,
        rewrite: (path) => path
      }
    }
  }
})
