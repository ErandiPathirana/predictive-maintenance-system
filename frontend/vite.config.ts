import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Read VITE_* variables from the single .env in the project root.
  envDir: "..",
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // These tests type into 14 fields with a simulated user, which takes 2-6 s on a normal laptop. The default 5 s limit made them time out on a slower machine, which is not a defect in the app.
    testTimeout: 30000,
  },
});
