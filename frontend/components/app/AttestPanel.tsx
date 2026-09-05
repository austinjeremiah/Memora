"use client";

import { useState } from "react";
import { useAccount, useSignTypedData } from "wagmi";
import {
  attestHandoff, getAttestationPayload, verifyAttestation,
} from "@/lib/api/client";
import {
  ApproveClaimIn, AttestationOut, AttestationPayloadOut,
  AttestationVerifyOut, MemoraApiError, Situation,
} from "@/lib/api/types";
import ConnectWallet from "./ConnectWallet";
import { Badge, Button, Card, Mono, Notice, Section, StatTile } from "./ui";

/**
 * Clinician attestation, two steps.
 *
 * The SERVER derives the state hash, because doing so means re-verifying every
 * claim against live Sibyl state — a browser cannot be trusted to decide what
 * was approved. The wallet only signs what memory has already justified, and
 * the server relays the transaction, so the signing account never pays gas.
 *
 * Without a connected wallet the server signs with a synthetic demo key. That
 * fallback is labelled as such everywhere, including in the API response's
 * `signer_kind`, because a demo key is not a clinician identity.
 */
export default function AttestPanel({ patientId, situation, clinicianId, claims }: {
  patientId: string;
  situation: Situation;
  clinicianId: string;
  claims: ApproveClaimIn[];
}) {
  const { address, isConnected } = useAccount();
  const { signTypedDataAsync } = useSignTypedData();

  const [payload, setPayload] = useState<AttestationPayloadOut | null>(null);
  const [result, setResult] = useState<AttestationOut | null>(null);
  const [verified, setVerified] = useState<AttestationVerifyOut | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const body = () => ({
    patient_id: patientId, situation, clinician_id: clinicianId, claims,
  });

  const prepare = async () => {
    setBusy("Re-verifying every claim against live memory…");
    setError(null);
    try {
      setPayload(await getAttestationPayload(patientId, body()));
    } catch (e) {
      setError((e as MemoraApiError).detail);
    } finally {
      setBusy(null);
    }
  };

  const sign = async () => {
    if (!payload) return;
    setError(null);
    try {
      let signature: string | undefined;
      let signer: string | undefined;

      if (isConnected && address) {
        setBusy("Waiting for your wallet…");
        // The typed data is built by the SERVER and arrives as plain JSON, so
        // its shape is not statically known here. One cast at the boundary is
        // honest about that; casting each field separately collapses the whole
        // argument to `never` and type-checks nothing.
        const typedData = {
          domain: payload.domain,
          types: payload.types,
          primaryType: payload.primary_type,
          message: {
            ...payload.message,
            // uint256 must be a bigint for viem; the hashes stay hex strings.
            nonce: BigInt(payload.message.nonce as number),
          },
        } as unknown as Parameters<typeof signTypedDataAsync>[0];

        signature = await signTypedDataAsync(typedData);
        signer = address;
      }

      setBusy("Submitting to Base Sepolia…");
      const res = await attestHandoff(patientId, {
        ...body(),
        ...(signature && signer ? {
          signature, signer,
          issued_at: payload.issued_at,
          expires_at: payload.expires_at,
          nonce: payload.nonce,
        } : {}),
      });
      setResult(res);

      setBusy("Reading it back from the chain…");
      setVerified(await verifyAttestation(res.state_hash));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError((e as MemoraApiError).detail ?? msg);
    } finally {
      setBusy(null);
    }
  };

  if (result) {
    return (
      <Section title="Attested on Base Sepolia">
        <Card>
          <div className="stack">
            <div className="grid grid--3">
              <StatTile label="Signed by" value={result.clinician_id}
                        hint={result.signer_kind === "registered_wallet"
                          ? "a registered wallet" : "synthetic demo key"} />
              <StatTile label="Memory version" value={result.memory_version}
                        hint="the state this signature is bound to" />
              <StatTile label="Block" value={result.block_number}
                        hint={`${result.gas_used} gas`} />
            </div>

            <div className="stack stack--tight">
              <span className="field__label">Signer</span>
              <Mono>{result.signer}</Mono>
              <span className="field__label" style={{ marginTop: 6 }}>
                Relayer — paid gas, did NOT sign
              </span>
              <Mono>{result.relayer}</Mono>
              <span className="field__label" style={{ marginTop: 6 }}>State hash</span>
              <Mono>{result.state_hash}</Mono>
            </div>

            {verified && (
              <Notice tone={verified.exists ? "info" : "error"}
                      title={verified.exists ? "Read back from the chain" : "Not found onchain"}>
                {verified.exists ? (
                  <>
                    The contract confirms this state was attested by{" "}
                    <Mono truncate={14}>{verified.signer}</Mono>
                    {verified.clinician_id && ` (${verified.clinician_id})`} at
                    memory version {verified.memory_version}. No clinical content
                    went onchain — only this digest.
                  </>
                ) : "The transaction succeeded but the state does not read back."}
              </Notice>
            )}

            <div className="row">
              <Button href={result.basescan_url} variant="primary">View on Basescan</Button>
            </div>
          </div>
        </Card>
      </Section>
    );
  }

  return (
    <Section title="Attest">
      <Card>
        <div className="stack">
          <ConnectWallet />

          {error && <Notice tone="error" title="Refused">{error}</Notice>}

          {!payload ? (
            <div className="row">
              <Button variant="primary" onClick={() => void prepare()} disabled={!!busy}>
                {busy ?? "Prepare attestation"}
              </Button>
              <span className="dim">
                {claims.length} claims · the server re-checks each one before anything is signed
              </span>
            </div>
          ) : (
            <div className="stack">
              <div className="row" style={{ gap: 8 }}>
                <Badge tone={payload.signer_mode === "wallet" ? "accent" : "neutral"}>
                  {payload.signer_mode === "wallet"
                    ? "registered wallet" : "synthetic demo key"}
                </Badge>
                <span className="dim">
                  nonce {payload.nonce} · expires in{" "}
                  {payload.expires_at - payload.issued_at}s · memory version{" "}
                  {payload.memory_version}
                </span>
              </div>

              <div className="stack stack--tight">
                <span className="field__label">What gets signed — all hashes</span>
                <Mono>{`stateHash    ${payload.state_hash}`}</Mono>
                <Mono>{`evidenceRoot ${payload.evidence_root}`}</Mono>
                <Mono>{`contextHash  ${payload.context_hash}`}</Mono>
              </div>

              {isConnected && payload.signer_mode !== "wallet" && (
                <Notice tone="warn" title="This wallet is not registered">
                  A wallet may only sign as a clinician it is mapped to in
                  <code className="mono"> CLINICIAN_WALLETS</code>. Without a
                  mapping the server will sign with the synthetic demo key
                  instead — a valid signature from an unregistered address is
                  refused on purpose.
                </Notice>
              )}

              <div className="row">
                <Button variant="primary" onClick={() => void sign()} disabled={!!busy}>
                  {busy ?? (isConnected ? "Sign and anchor" : "Anchor with demo key")}
                </Button>
                <span className="dim">
                  The relayer pays gas — your wallet needs no balance
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>
    </Section>
  );
}
