import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // API Gateway 역방향 프록시 (개발 환경)
  async rewrites() {
    const apiGateway = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiGateway}/:path*`,
      },
    ];
  },
  // 실험적: 서버 컴포넌트 / App Router 최적화
  experimental: {
    optimizePackageImports: ["recharts"],
  },
};

export default nextConfig;
