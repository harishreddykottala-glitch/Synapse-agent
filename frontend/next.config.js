/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://localhost:8000/api/:path*',
            },
            {
                source: '/chat',
                destination: 'http://localhost:8000/chat',
            },
        ];
    },
};

module.exports = nextConfig;
