"use client";

import { useState } from "react";
import {
  getClinicians, getHealth, getPatientMemory, getReadyz,
  listPatients, requestHandoff, runSentinel,
} from "@/lib/api/client";
import { MemoraApiError } from "@/lib/api/types";
import { getApiBaseUrl } from "@/lib/api/baseUrl";
import {
  Badge, Button, Card, Mono, Notice, Section, StatTile,
} from "@/components/app/ui";

/**
 * The hackathon's own pass/fail criterion, runnable.
 *
 *   "delete the Sibyl Memory layer. Does the project still do what it claims?
 *    If yes, it is not load-bearing, and it is disqualified."
 *
 * This page probes every endpoint and shows what each one does. With memory
 * present, the clinical endpoints answer. With memory deleted they must refuse
 * with 503 -- not return an empty result that looks like success.
 *
 * That distinction is not hypothetical: sibyl-memory-client silently RECREATES
 * an empty store when memory.db is missing, so without an explicit guard
 * MEMORA would have answered 200 with nothing and failed this criterion while
 * every test stayed green.
 */

type Probe = {
  name: string;
  path: string;
  clinical: boolean;   // does it need the memory layer?
  run: () => Promise<unknown>;
};

type Result =
  | { state: "ok"; detail: string }
  | { state: "refused"; code: string; detail: string }
  | { state: "error"; detail: string };

export default function ProofPage() {
  const [results, setResults] = useState<Record<string, Result>>({});
  const [running, setRunning] = useState(false);
  const [ranAt, setRanAt] = useState<string | null>(null);

  const probes: Probe[] = [
    { name: "Liveness", path: "GET /health", clinical: false,
      run: () => getHealth() },
    { name: "Readiness", path: "GET /readyz", clinical: true,
      run: () => getReadyz() },
    { name: "Clinicians", path: "GET /clinicians", clinical: false,
      run: () => getClinicians() },
    { name: "Patient discovery", path: "GET /patients", clinical: true,
      run: () => listPatients() },
    { name: "Stored memory", path: "GET /patients/{id}/memory", clinical: true,
      run: async () => {
        const list = await listPatients();
        if (!list.length) throw new Error("no patients in the store");
        return getPatientMemory(list[0].patient_id, 1);
      } },
    { name: "Handover brief", path: "POST /handoff", clinical: true,
      run: async () => {
        const list = await listPatients();
        if (!list.length) throw new Error("no patients in the store");
        return requestHandoff({
          patient_id: list[0].patient_id, situation: "icu_to_ward",
          clinician_id: "dr_maya",
        });
      } },
    { name: "Sentinel sweep", path: "POST /sentinel/run", clinical: true,
      run: () => runSentinel({ situation: "icu_to_ward" }) },
  ];

  const probeAll = async () => {
    setRunning(true);
    setResults({});
    for (const p of probes) {
      try {
        await p.run();
        setResults((r) => ({ ...r, [p.name]: { state: "ok", detail: "answered" } }));
      } catch (e) {
        const err = e as MemoraApiError;
        if (err.code === "sibyl_unavailable") {
          setResults((r) => ({ ...r, [p.name]: {
            state: "refused", code: err.code, detail: err.detail } }));
        } else {
          setResults((r) => ({ ...r, [p.name]: {
            state: "error", detail: err.detail ?? String(e) } }));
        }
      }
    }
    setRanAt(new Date().toLocaleTimeString());
    setRunning(false);
  };

  const clinical = probes.filter((p) => p.clinical);
  const answered = clinical.filter((p) => results[p.name]?.state === "ok").length;
  const refused = clinical.filter((p) => results[p.name]?.state === "refused").length;
  const done = Object.keys(results).length === probes.length;

  return (
    <div className="stack stack--loose">
      <div className="stack stack--tight">
        <h1 className="page-title">Endpoint probe</h1>
        <p className="subtle" style={{ margin: 0, maxWidth: 700 }}>
          Calls every endpoint and shows what came back. Run it once with the
          store in place, then delete <code className="mono">memory.db</code> and
          run it again: every clinical endpoint should <strong>refuse</strong>,
          rather than return an empty result that reads like an answer.
        </p>
      </div>

      <Notice tone="warn" title="Why the store is checked before it is opened">
        <code className="mono">MemoryClient.local()</code> silently{" "}
        <strong>recreates</strong> an empty store when{" "}
        <code className="mono">memory.db</code> is missing. It does not raise. So
        the file is checked before the client is constructed; without that,
        MEMORA would answer 200 from an empty store while every test stayed
        green.
      </Notice>

      <Card>
        <div className="stack">
          <div className="row row--between">
            <span className="dim">
              Probing <Mono>{getApiBaseUrl()}</Mono>
            </span>
            <Button variant="primary" onClick={() => void probeAll()} disabled={running}>
              {running ? "Probing…" : ranAt ? "Probe again" : "Probe every endpoint"}
            </Button>
          </div>

          {done && (
            <div className="grid grid--3">
              <StatTile icon="database" label="Clinical endpoints" value={clinical.length}
                        hint="these require the memory layer" />
              <StatTile icon="seal" label="Answered" value={answered}
                        hint={answered === clinical.length ? "memory is present" : ""} />
              <StatTile icon="shield" tone="amber" label="Refused" value={refused}
                        hint={refused === clinical.length ? "memory is gone — correct" : ""} />
            </div>
          )}
        </div>
      </Card>

      <Section title="Endpoints" action={ranAt ? <span className="dim">ran {ranAt}</span> : undefined}>
        <Card flush>
          <div className="scroll-x">
            <table className="table">
              <thead>
                <tr><th>Endpoint</th><th>Needs memory</th><th>Result</th></tr>
              </thead>
              <tbody>
                {probes.map((p) => {
                  const r = results[p.name];
                  return (
                    <tr key={p.name}>
                      <td>
                        <div className="stack stack--tight">
                          <span>{p.name}</span>
                          <Mono>{p.path}</Mono>
                        </div>
                      </td>
                      <td>{p.clinical ? <Badge tone="accent">yes</Badge>
                                       : <Badge>no</Badge>}</td>
                      <td>
                        {!r && <span className="dim">not probed</span>}
                        {r?.state === "ok" && <Badge tone="allow">answered</Badge>}
                        {r?.state === "refused" && (
                          <div className="stack stack--tight">
                            <Badge tone="review">503 refused</Badge>
                            <span className="dim">{r.detail.slice(0, 90)}</span>
                          </div>
                        )}
                        {r?.state === "error" && (
                          <div className="stack stack--tight">
                            <Badge tone="block">error</Badge>
                            <span className="dim">{r.detail.slice(0, 90)}</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </Section>

      {done && refused === clinical.length && (
        <Notice tone="warn" title="Memory is gone, and MEMORA refused">
          Every clinical endpoint returned 503. Nothing answered from an empty
          store, and the store was not silently recreated.
        </Notice>
      )}

      {done && answered === clinical.length && (
        <Notice title="Memory is present — everything answers">
          Now stop the API, delete its <code className="mono">memory.db</code>, restart it
          and probe again. The clinical rows should all turn to 503.
          <p style={{ marginBottom: 0, marginTop: 8 }}>
            The same check runs automatically in{" "}
            <code className="mono">tests/compliance/test_deletion.py</code> and as
            the final stage of{" "}
            <code className="mono">scripts/e2e_full.sh</code>.
          </p>
        </Notice>
      )}
    </div>
  );
}
