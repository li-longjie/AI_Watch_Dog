import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/video_feed': {
        target: 'ws://localhost:16532',
        ws: true,
        changeOrigin: true,
      },
      '/alerts': {
        target: 'ws://localhost:16532',
        ws: true,
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:16532',
        changeOrigin: true,
      },
      '/test_alert': {
        target: 'http://localhost:16532',
        changeOrigin: true,
      },
      '/video_warning': {
        target: 'http://localhost:16532',
        changeOrigin: true,
      }
    }
  }
})
