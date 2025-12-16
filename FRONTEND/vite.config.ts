import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    port: 3000,
    allowedHosts: [
      'reuniones.frumecar.com',
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/audio': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/upload_audio': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/upload_and_create_meeting': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/upload_and_process_directly': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/process_final_audio': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/identify_speakers': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/direct_summarize_transcript': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/verify_password': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/rename_reunion': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/delete_reunion': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  }
})