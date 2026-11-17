import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: process.env.LOAD_DOTENV === "false" ? false : undefined,
  preview: {
    allowedHosts: ['ai-code-review-agent-1-7tzq.onrender.com'],
  },
})
