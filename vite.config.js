import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import devApi from './dev-api.js';

// WebAuthn only works on https or http://localhost — keep using localhost.
export default defineConfig({
  plugins: [react(), devApi()],
  server: { port: 5173, host: 'localhost', strictPort: false },
  preview: { port: 4173, host: 'localhost' },
});
