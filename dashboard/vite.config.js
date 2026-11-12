import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// In dev, /api is forwarded to the FastAPI server (uvicorn on :8000).
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
