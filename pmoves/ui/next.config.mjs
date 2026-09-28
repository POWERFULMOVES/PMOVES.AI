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
  // Next 16 writes AGENTS.md and CLAUDE.md into this folder on every `next dev`
  // start. Those files carry vendor instructions that coding-agent sessions
  // (Claude Code included) then load as project instructions. This is the
  // documented opt-out (next/dist/docs/01-app/02-guides/ai-agents.md).
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
