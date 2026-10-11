import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Workaround: vite 8's rolldown-based emptyOutDir silently kills the
    // build on Windows when dist/ already exists (render never runs, build
    // exits with code 127 / 0 and writes nothing). Skipping the empty step
    // keeps iterative local builds working; hashed asset names mean stale
    // files from earlier builds are simply unused. `rm -rf dist` restores a
    // perfectly clean output whenever wanted.
    emptyOutDir: false,
  },
  server: {
    port: 5173,
    proxy: {
      // Forward API calls to the FastAPI backend during development.
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
