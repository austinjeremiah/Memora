"use client";

import { useEffect, useState } from "react";
import { askMemory, getClinicians } from "@/lib/api/client";
import { AskOut, ClinicianOut, MemoraApiError, SessionInfluenceOut } from "@/lib/api/types";
import ClaimCard, { GateSummary } from "./ClaimCard";
import MatchedRecords from "./MatchedRecords";
import { Badge, Button, Card, Notice, Section, SkeletonList } from "./ui";

/**
 * What memory written before this session did to this answer.
 *
 * Only rendered when it actually changed something. A panel that appeared on
 * every answer saying "0 prior sessions considered" would be the decorative
 * integration the rules disqualify -- the claim is only worth making when
 * there is a changed verdict to point at.
 */
function Influence({ influence }: { influence: SessionInfluenceOut }) {
  if (!influence.changed_the_answer) return null;
  const dead = influence.sessions_from_dead_processes;

  return (
    <div className="influence">
      <div className="influence__head">
        <span className="influence__title">This answer was changed by earlier memory</span>
        <Badge tone="allow">
          {influence.crossed_restart ? "recalled across a restart" : "same process"}
        </Badge>
      </div>
      <span className="dim">
        {influence.prior_sessions} prior session{influence.prior_sessions === 1 ? "" : "s"}
        {dead > 0 && <> · {dead} written by {dead === 1 ? "a process" : "processes"} that has since ended</>}
        {" · this process "}{influence.current_boot_id}
      </span>
      {influence.changed_claims.map((c) => (
        <p key={c} className="influence__claim">{c}</p>
      ))}
      {influence.shaping_events.slice(0, 3).map((e, i) => (
        <div key={`${e.source_id ?? i}-${i}`} className="recall__item">
          <span className="recall__when">{e.timestamp.slice(0, 10)}</span>
          <span className="recall__what">{e.summary}</span>
        </div>
      ))}
    </div>
  );
}

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
export default function AskMemory({ patientId, threadId, clinicianId: pinned }: {
  patientId: string;
  /** When inside a session, the question is recorded on this thread. */
  threadId?: string | null;
  /** Inside a session the clinician is the session's, not a local choice. */
  clinicianId?: string | null;
}) {
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
    const who = pinned || clinicianId;
    if (text.length < 3 || !who) return;
    setQuestion(text);
    setAsking(true);
    setError(null);
    setResult(null);
    try {
      setResult(await askMemory(patientId, {
        question: text, clinician_id: who, thread_id: threadId ?? null,
      }));
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
            {!pinned && (
              <select className="select" style={{ width: 170 }} value={clinicianId}
                      onChange={(e) => setClinicianId(e.target.value)} disabled={!clinicians}>
                {clinicians?.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
            <Button variant="primary" onClick={() => void ask()}
                    disabled={asking || question.trim().length < 3 || !(pinned || clinicianId)}>
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

              {result.influence && <Influence influence={result.influence} />}

              {!result.answered ? (
                <Notice tone="warn" title="Memory does not answer this">
                  {result.matched.length === 0
                    ? "Nothing in this patient's record matches that question, so the model was never asked. Answering from an empty result set is how a confident fabrication happens."
                    : `The search matched ${result.matched.length} record${result.matched.length === 1 ? "" : "s"}, but none of them support an answer to this question — so nothing is asserted. The matched records are shown below exactly as stored, rather than summarised into prose that would read as an answer.`}
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

              {result.matched.length > 0 && <MatchedRecords matched={result.matched} />}
            </div>
          )}
        </div>
      </Card>
    </Section>
  );
}
