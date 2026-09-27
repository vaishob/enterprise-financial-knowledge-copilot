import type { NextConfig } from "next";

// Rewrites are compiled during next build. Set BACKEND_URL in the build environment.
const backend = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Bounded worker threads also support hosts that restrict child process creation.
  experimental: { workerThreads: true, cpus: 2, useTypeScriptCli: false },
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` },
      { source: "/api/ready", destination: `${backend}/ready` },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "same-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ] }];
  },
};
export default config;
