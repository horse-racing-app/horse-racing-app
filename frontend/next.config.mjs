/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        // フロントエンドへの /api/〜 のアクセスを
        source: '/api/:path*',
        // 裏側でこっそり環境変数のURLへ転送する（ローカル開発時は8080へ）
        destination: `${process.env.API_URL || 'http://127.0.0.1:8080'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;