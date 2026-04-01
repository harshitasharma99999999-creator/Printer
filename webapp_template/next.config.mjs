/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [
      { source: "/sw.js", headers: [{ key: "Service-Worker-Allowed", value: "/" }] },
      { source: "/manifest.json", headers: [{ key: "Content-Type", value: "application/manifest+json" }] },
    ];
  },
};
export default nextConfig;
