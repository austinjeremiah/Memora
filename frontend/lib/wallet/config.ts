"use client";

import { createConfig, http } from "wagmi";
import { baseSepolia } from "wagmi/chains";
import { injected } from "wagmi/connectors";

/**
 * Wallet configuration — Base Sepolia only.
 *
 * DELIBERATELY NOT RainbowKit. Its v2 `getDefaultConfig` requires a
 * WalletConnect `projectId`, which means depending on an external account
 * during a live demo, and it ships its own modal styling that would have to be
 * re-themed against the Framer tokens the rest of the app uses. An injected
 * connector covers MetaMask and Coinbase Wallet — which is what a demo runs on
 * — with no external dependency and no second design language.
 *
 * Only Base Sepolia is configured. The attestation contract lives there, and
 * an EIP-712 signature is bound to a chain id: signing on the wrong network
 * produces a signature the contract will reject.
 */
export const CHAIN = baseSepolia;

export const wagmiConfig = createConfig({
  chains: [baseSepolia],
  connectors: [injected()],
  transports: {
    [baseSepolia.id]: http("https://sepolia.base.org"),
  },
  ssr: true,
});
