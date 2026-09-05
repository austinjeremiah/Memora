"use client";

import { useAccount, useConnect, useDisconnect, useSwitchChain } from "wagmi";
import { CHAIN } from "@/lib/wallet/config";
import { Badge, Button, Notice } from "./ui";

/**
 * Connect a wallet to sign attestations.
 *
 * The wallet only ever SIGNS. It never pays gas — the server relays — so the
 * connected account needs no balance. That separation is the point: the
 * signature proves who approved, the relayer proves nothing.
 */
export default function ConnectWallet() {
  const { address, isConnected, chainId } = useAccount();
  const { connect, connectors, isPending, error } = useConnect();
  const { disconnect } = useDisconnect();
  const { switchChain } = useSwitchChain();

  const injected = connectors[0];
  const wrongChain = isConnected && chainId !== CHAIN.id;

  if (!isConnected) {
    return (
      <div className="stack stack--tight">
        <div className="row">
          <Button variant="primary" disabled={isPending || !injected}
                  onClick={() => injected && connect({ connector: injected })}>
            {isPending ? "Connecting…" : "Connect wallet"}
          </Button>
          <span className="dim">
            Signing only — no gas, no balance needed
          </span>
        </div>
        {!injected && (
          <Notice tone="warn" title="No browser wallet detected">
            Install MetaMask or Coinbase Wallet, or continue without one — the
            server will sign with a synthetic demo key instead.
          </Notice>
        )}
        {error && <Notice tone="error" title="Could not connect">{error.message}</Notice>}
      </div>
    );
  }

  return (
    <div className="stack stack--tight">
      <div className="row" style={{ gap: 10 }}>
        <Badge tone="allow">connected</Badge>
        <span className="mono">{address?.slice(0, 10)}…{address?.slice(-6)}</span>
        <Button size="sm" variant="ghost" onClick={() => disconnect()}>Disconnect</Button>
      </div>
      {wrongChain && (
        <Notice tone="warn" title={`Switch to ${CHAIN.name}`}>
          An EIP-712 signature is bound to a chain id. Signing on the wrong
          network produces a signature this contract will reject.
          <div className="row" style={{ marginTop: 10 }}>
            <Button size="sm" onClick={() => switchChain({ chainId: CHAIN.id })}>
              Switch to {CHAIN.name}
            </Button>
          </div>
        </Notice>
      )}
    </div>
  );
}
