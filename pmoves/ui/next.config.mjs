import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Default '.next' is unchanged for dev, build, and the Docker image.
  // PMOVES_UI_DIST_DIR exists only so playwright.launcher.config.ts can run two
  // dev servers (real room catalog + negative fixture catalog) side by side:
  // Next 16 refuses a second `next dev` that shares a distDir.
  distDir: process.env.PMOVES_UI_DIST_DIR || '.next',
  // The repo follows the AGENTS.md convention (per-directory AGENTS.md files
  // are hand-written and allowed), so we stop Next from generating its own
  // copy instead of ignoring the filename. Next 16 otherwise writes AGENTS.md
  // and CLAUDE.md here on `next dev`, carrying vendor instructions that
  // coding-agent sessions load as project instructions. Documented opt-out:
  // next/dist/docs/01-app/02-guides/ai-agents.md. scripts/check-agent-rules.mjs
  // (ui-tests lint job) fails if a generated block is ever committed.
  agentRules: false,
  output: 'standalone',
  reactStrictMode: true,
  outputFileTracingRoot: __dirname,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'i.ytimg.com',
        pathname: '/vi/**',
      },
      {
        protocol: 'https',
        hostname: 'img.youtube.com',
        pathname: '/vi/**',
      },
      {
        protocol: 'https',
        hostname: '*.googleusercontent.com',
      },
      {
        protocol: 'https',
        hostname: '*.ggpht.com',
      },
      {
        protocol: 'https',
        hostname: 'localhost',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
};

export default nextConfig;
