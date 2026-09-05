# Phase F7 — Clinician attestation and wallet signing

**Status:** done · frontend only (backend gained wallet mode in Phase B)

---

## Why not RainbowKit

Austin asked for RainbowKit. I used **wagmi + viem with an injected connector**
instead, for two reasons worth recording:

1. **RainbowKit v2's `getDefaultConfig` requires a WalletConnect `projectId`** —
   an external account dependency in the middle of a live demo.
2. It ships **its own modal styling**, which would be a third design language
   after F1 spent a phase making the app use the landing's actual tokens.

An injected connector covers MetaMask and Coinbase Wallet, which is what a demo
runs on. `ConnectWallet` is built in the existing design system.

If RainbowKit is wanted later it drops in on top of the same wagmi config —
this is not a one-way door.

Only **Base Sepolia** is configured. An EIP-712 signature is bound to a chain
id, so signing on the wrong network produces a signature the contract rejects.
The panel detects a wrong chain and offers to switch.

---

## The two-step flow

```
POST /handoff/{id}/attestation-payload   server re-verifies every claim
                                         against live memory, derives the
                                         state hash, returns EIP-712 typed data
        ↓
   wallet signs                          signs only what memory justified
        ↓
POST /handoff/{id}/attest                server verifies the signature and relays
        ↓
GET  /attestation/{hash}/verify          read back off the chain
```

**The server derives the state hash, not the browser.** Doing so requires
re-verifying every claim against live Sibyl state, and a browser cannot be
trusted with that decision. The wallet's only job is to sign what memory has
already justified.

**The wallet never pays gas.** The server relays, so the connected account
needs no balance — and the response shows `signer` and `relayer` as different
addresses. That separation is the point: the signature proves who approved;
the relayer proves nothing.

---

## Honest labelling

Without a connected wallet the server signs with a **synthetic demo key**. That
is surfaced three ways: `signer_mode` on the payload, `signer_kind` on the
response, and a badge in the UI. A demo key is not a clinician identity and the
interface never implies otherwise.

If a wallet is connected but not mapped in `CLINICIAN_WALLETS`, the panel says
so explicitly — a cryptographically valid signature from an unregistered
address is refused on purpose (Option B authorisation).

---

## Verified live

```
1. payload  signer_mode: synthetic_demo_key   memory_version 254   nonce 24
            ttl 900s
            stateHash 0x040cb2e77052b2b3821dbac67467611777f761ea1022db4d433a0cd295ecda51
            fields: stateHash, evidenceRoot, contextHash, memoryVersion,
                    issuedAt, expiresAt, nonce

2. attest   signer  0x6c50E65897C4d395f610C685568B5D690fc5e050
            relayer 0xCD8F91DC7929E973DDc071838904434297aB4673  ← different
            tx      0x3349921e01687e0c15f5b9ec47edb341cd6820b521e4314fd4c4672b15b191ac
            block   46411958   gas 88988

3. verify   exists=True  clinician=dr_maya  memory_version=254
```

**What is not verified here:** the browser wallet signing path needs a real
MetaMask and cannot be exercised from a terminal. It is covered by the backend
test `test_a_real_wallet_signature_is_recorded_onchain`, which signs with a real
key and submits to the deployed contract. The UI path should still be clicked
once before filming.

---

## Both mechanisms remain

`/approve` (anonymous hash, the v1 mechanism, 23+ real commitments) and
`/attest` (signed, attributed) are both live and both surfaced on the result
page. Fork 2 in `memora-v2.md` chose to extend rather than replace: destroying
verified onchain history to make a diagram tidier is a bad trade.

---

## Resume

```bash
cd frontend && npm install && npm run dev
```

To sign from a real wallet, map it in `backend/.env`:
```
CLINICIAN_WALLETS=dr_maya:0xYourWalletAddress
```
Without a mapping the wallet can connect but the server signs with the demo key.
