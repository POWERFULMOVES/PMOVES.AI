/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require("fs");
const path = require("path");
const dotenv = require("dotenv");

const envPath = path.resolve(__dirname, "../.env.local");
if (fs.existsSync(envPath)) {
  dotenv.config({ path: envPath });
}

const publicEnv = {};

const assignEnv = (targetKey, value) => {
  if (typeof value === "string" && value.length > 0) {
    publicEnv[targetKey] = value;
  }
};

assignEnv("NEXT_PUBLIC_SUPABASE_URL", process.env.SUPABASE_URL);
assignEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", process.env.SUPABASE_ANON_KEY);
assignEnv("NEXT_PUBLIC_SUPABASE_REST_URL", process.env.SUPABASE_REST_URL);
assignEnv("NEXT_PUBLIC_SUPABASE_REALTIME_URL", process.env.SUPABASE_REALTIME_URL);
assignEnv("NEXT_PUBLIC_PMOVES_API_URL", process.env.PMOVES_API_URL);
assignEnv("NEXT_PUBLIC_PMOVES_WS_URL", process.env.PMOVES_WS_URL);

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: publicEnv,
};

module.exports = nextConfig;
