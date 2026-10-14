import { defineConfig } from 'vite';
import { resolve } from 'node:path';
export default defineConfig({
  publicDir: 'public',
  build: { outDir: 'dist', emptyOutDir: true, rollupOptions: { input: { popup: resolve(__dirname, 'index.html'), background: resolve(__dirname, 'src/background.ts'), content: resolve(__dirname, 'src/content/legacy.ts') }, output: { entryFileNames: (chunk) => chunk.name === 'popup' ? 'assets/[name].js' : '[name].js' } } }
});
