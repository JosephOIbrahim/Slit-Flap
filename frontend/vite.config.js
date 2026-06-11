import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:4040'
    }
  },
  build: {
    // Build straight into the Python package so `pip install` ships the board
    outDir: '../departures/frontend/dist',
    emptyOutDir: true
  }
})
