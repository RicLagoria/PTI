import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    proxy: {
      // Igual que el nginx de Docker: /api/* -> ia-entrenamiento-api sin el prefijo /api
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // El login lo valida cliente-api, no el plano IA: acá se mantiene el
      // prefijo porque sus endpoints ya se llaman /auth/login y /auth/yo.
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
