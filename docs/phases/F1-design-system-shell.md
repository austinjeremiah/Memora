# Phase F1 — App design system and shell

**Status:** done · frontend only (no backend changes)

The first frontend phase. Establishes one visual language for every app page
and fixes two things the existing scaffold got wrong.

---

## The problem

The repo had two unrelated design languages:

- **Landing** — a Framer export. `framer-13xxj9k`-style generated class names,
  679 lines of CSS, Inter / Inter Display / Edgar Sigma.
- **`/app` pages** — raw inline styles, `#050608` background, `sans-serif`.

They looked like two different products. But Framer's CSS is generated
class-soup and cannot be reused for data-dense clinical tables.

**Decision: lift the values, not the class names.** The tokens below were read
out of the landing's own CSS, so the app matches it without depending on its
markup.

---

## What shipped

### `frontend/styles/app.css` — 185 lines of tokens

```css
--bg          rgb(12, 15, 22)             /* landing page ground        */
--bg-elevated rgba(6, 7, 10, 0.95)        /* landing card background    */
--accent      rgb(1, 117, 255)            /* brand blue                 */
--border      rgba(125, 164, 255, 0.16)   /* the signature hairline     */
--text / --text-secondary / --text-muted / --text-dim   /* the 4-step ramp */
--allow  rgb(74, 222, 128)                /* gate verdicts — semantic,  */
--review rgb(255, 205, 125)               /* not decorative. These three */
--block  rgb(255, 107, 107)               /* carry the product's meaning */
--r-pill 999px   --r-lg 24px              /* the landing's own radii     */
```

Plus base classes: `.app-root`, `.app-nav`, `.card`, `.btn`, `.badge`,
`.field`, `.notice`, `.meter`, `.table`, `.skeleton`, `.stack`, `.row`, `.grid`.

### `frontend/components/app/ui.tsx` — the shared kit

`Card` · `Section` · `GateBadge` · `Badge` · `Button` · `Field` · `Notice` ·
`QuotaMeter` · `Mono` · `Skeleton` · `SkeletonList` · `EmptyState` ·
`StatTile` · `SeverityDot`

Every page composes from here. **No page renders a raw inline style.**

### Shell restyled

- `app/app/layout.tsx` — uses `.app-root` / `.app-main`
- `app/app/AppNav.tsx` — sticky, pill links, Edgar Sigma wordmark
- `app/app/StatusStrip.tsx` — live backend/Sibyl dots + quota meter
- `app/app/page.tsx` — rewritten as a **status-first** page

The status page opens by answering *is the memory layer alive?* rather than
showing a dashboard. That framing is deliberate: MEMORA's claim is that it
cannot answer without Sibyl, so the app should show whether Sibyl is there.

---

## Two things fixed rather than shipped

### The stale quota constant is gone entirely

`StatusStrip` had `FREE_TIER_CAP_BYTES = 2_097_152` — the figure from Sibyl's
own docs, and wrong. The real cap is 5,242,880.

It was **not** corrected to the right number. The constant was removed:
`AppStatusContext` now carries `soft_cap_bytes` from the backend response
(`reportDbSize` → `reportMemory`). A frontend constant mirroring a backend fact
goes stale silently, and this one already had.

### The nav would have shipped two 404s

The first draft linked `/app/patients` and `/app/sentinel`, which do not exist
until F3 and F6. **A link is added only when its page lands** — a shorter nav
beats a broken one. Both slot into the existing order when built.

---

## Verified — both servers running, real data

```
backend  /health              {"status":"ok","service":"memora"}
frontend /app                 HTTP 200
CORS preflight (from :3000)   access-control-allow-origin: http://localhost:3000
GET /patients via that origin 0c33684a… 97 facts v253
                              c1735287… 93 facts v222
                              f5fe5e84… 95 facts v226
shell classes present         app-root · app-nav · page-title · card · btn--primary
design tokens in bundle       --accent · --allow · --border   (fe9a7871….css, 6.4 KB)
next build                    7 routes, all static, no errors
tsc --noEmit                  clean
backend suite                 255 passed (unaffected)
```

CORS was already configured (added in `dcd5b19`), so browser calls work.

---

## Deliberately not done yet

| Missing | Phase |
|---|---|
| Sentinel + Attestation types and client functions | F2 |
| `listPatients()` / `getPatientHistory()` still throw | F2 |
| Patients list, memory explorer | F3 |
| Handoff + compare pages still on old inline styles | F4, F5 |
| Wallet / RainbowKit | F7 |

`lib/api/client.ts` still covers only 5 of the backend's 14 routes.

---

## Resume

```bash
cd backend && scripts/run_api.sh          # :8000
cd frontend && npm run dev                # :3000  → http://localhost:3000/app
```

To point the API at a store with real patients:
```bash
SIBYL_DB_PATH=/path/to/memory.db scripts/run_api.sh
```
