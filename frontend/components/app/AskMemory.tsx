"use client";

import { useEffect, useState } from "react";
import { askMemory, getClinicians } from "@/lib/api/client";
import { AskOut, ClinicianOut, MemoraApiError } from "@/lib/api/types";
import ClaimCard, { GateSummary } from "./ClaimCard";
import { Badge, Button, Card, Mono, Notice, Section, SkeletonList } from "./ui";

const SUGGESTIONS = [
  "Can I restart this medication?",
  "Are there any documented drug allergies?",
  "Is renal function stable?",
];

/**
 * Ask memory a question.
 *
 * Not a chatbot. A chat invites free-form generation, which is the failure the
 * gate exists to prevent -- it would be building the problem and the solution
 * in the same feature. This retrieves from memory by keyword, lets the model
 * propose an answer citing what was found, and puts every claim through the
 * same Evidence Resolver and Gate as a handover brief.
 *
 * The interesting outcome is the refusal: ask something memory cannot support
 * and it says so, rather than producing fluent prose.
 */
export default function AskMemory({ patientId }: { patientId: string }) {
  const [question, setQuestion] = useState("");
  const [clinicianId, setClinicianId] = useState("");
  const [clinicians, setClinicians] = useState<ClinicianOut[] | null>(null);
  const [result, setResult] = useState<AskOut | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<MemoraApiError | null>(null);

  useEffect(() => {
    getClinicians().then((list) => {
      setClinicians(list);
      if (list.length) setClinicianId((c) => c || list[0].id);
    }).catch(() => undefined);
  }, []);

  const ask = async (q?: string) => {
    const text = (q ?? question).trim();
    if (text.length < 3 || !clinicianId) return;
    setQuestion(text);
    setAsking(true);
    setError(null);
    setResult(null);
    try {
      setResult(await askMemory(patientId, { question: text, clinician_id: clinicianId }));
    } catch (e) {
      setError(e as MemoraApiError);
    } finally {
      setAsking(false);
    }
  };

  return (
    <Section
      title="Ask this patient's memory"
      action={<Badge tone="accent">FTS5 search · gated answer</Badge>}
    >
      <Card>
        <div className="stack">
          <div className="row" style={{ gap: 10 }}>
            <input
              className="input"
              style={{ flex: 1, minWidth: 240 }}
              value={question}
              placeholder="e.g. Can I restart warfarin?"
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void ask()}
            />
            <select className="select" style={{ width: 170 }} value={clinicianId}
                    onChange={(e) => setClinicianId(e.target.value)} disabled={!clinicians}>
              {clinicians?.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <Button variant="primary" onClick={() => void ask()}
                    disabled={asking || question.trim().length < 3}>
              {asking ? "Searching memory…" : "Ask"}
            </Button>
          </div>

          {!result && !asking && (
            <div className="row" style={{ gap: 8 }}>
              <span className="dim">Try:</span>
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="btn btn--ghost btn--sm"
                        onClick={() => void ask(s)}>{s}</button>
              ))}
            </div>
          )}

          {error && (
            <Notice tone="error"
                    title={error.code === "sibyl_unavailable"
                      ? "MEMORA cannot reach its memory layer"
                      : error.code === "llm_unavailable"
                        ? "The model provider is unreachable"
                        : "Could not answer"}>
              {error.detail}
            </Notice>
          )}

          {asking && <SkeletonList rows={2} />}

          {result && (
            <div className="stack">
              <div className="row" style={{ gap: 8 }}>
                <span className="dim">searched for</span>
                {result.search_terms.length
                  ? result.search_terms.map((t) => <Badge key={t}>{t}</Badge>)
                  : <span className="dim">nothing searchable in that question</span>}
                <span className="dim">
                  · {result.matched.length} record{result.matched.length === 1 ? "" : "s"} matched
                </span>
              </div>

              {!result.answered ? (
                <Notice tone="warn" title="Memory does not answer this">
                  {result.matched.length === 0
                    ? "Nothing in this patient's record matches that question, so the model was never asked. Answering from an empty result set is how a confident fabrication happens."
                    : "Records matched, but nothing the model proposed could be supported by them. Prose whose every claim was refused is a refusal, not an answer."}
                </Notice>
              ) : (
                <>
                  <Card tight>
                    <div className="stack stack--tight">
                      <span className="field__label">Answer</span>
                      <span style={{ fontSize: 15, lineHeight: 1.55 }}>{result.answer}</span>
                      <span className="dim">
                        {result.model} proposed this · every claim below was checked
                        against the record before it was shown
                      </span>
                    </div>
                  </Card>

                  <div className="row row--between">
                    <span className="field__label">Supporting claims</span>
                    <GateSummary claims={result.claims} />
                  </div>
                  <div className="stack">
                    {result.claims.map((c) => <ClaimCard key={c.text} claim={c} />)}
                  </div>
                </>
              )}

              {result.matched.length > 0 && (
                <details>
                  <summary className="dim" style={{ cursor: "pointer" }}>
                    What the search found in memory
                  </summary>
                  <div className="stack stack--tight" style={{ marginTop: 10 }}>
                    {result.matched.map((m) => (
                      <div key={`${m.kind}/${m.name}`} className="row" style={{ gap: 8 }}>
                        <Mono truncate={44}>{`${m.kind}/${m.name}`}</Mono>
                        {m.status && <Badge>{m.status}</Badge>}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      </Card>
    </Section>
  );
}
