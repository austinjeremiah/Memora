/** @type {import('next').NextConfig} */

/**
 * Optional peer dependencies of `@wagmi/connectors` that MEMORA does not use.
 *
 * `lib/wallet/config.ts` configures exactly one connector — `injected()` — but
 * importing it from `wagmi/connectors` pulls the package's whole barrel, which
 * statically references the SDKs for Coinbase, WalletConnect, Safe and
 * MetaMask. Those are optional peers and are not installed, so `next build`
 * failed to collect page data for every route under the wallet provider, while
 * `next dev` tolerated it — a production build that broke without the dev
 * server ever noticing.
 *
 * Aliasing them to false is the honest fix rather than installing four wallet
 * SDKs to satisfy imports on code paths that never execute.
 */
const UNUSED_WALLET_SDKS = [
  "@base-org/account",
  "@coinbase/wallet-sdk",
  "@metamask/connect-evm",
  "@safe-global/safe-apps-sdk",
  "@safe-global/safe-apps-provider",
  "@walletconnect/ethereum-provider",
  "accounts",
];

const nextConfig = {
  reactStrictMode: true,
  // Lets a verification build run without clobbering the .next directory a
  // running `next dev` is using. Unset in normal builds, including on Vercel.
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      ...Object.fromEntries(UNUSED_WALLET_SDKS.map((m) => [m, false])),
    };
    return config;
  },
};

export default nextConfig;
