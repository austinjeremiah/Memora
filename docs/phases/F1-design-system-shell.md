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

**First attempt was wrong.** I read colours off the landing by eye and
hardcoded them into a new palette. That produced a *lookalike*, not the same
theme — and it would drift the moment anything on the landing changed. Austin
caught it: the app nav was a flat bar where the landing has a floating glass
pill, and the wordmark was in the wrong typeface entirely.

**Corrected approach: alias the landing's own tokens.** The Framer export
publishes its real design tokens as CSS custom properties on `<body>`
(`--token-<uuid>`). `app.css` now references those directly, so changing a
token on the landing changes the app too. Fallbacks are each token's own
default, so pages still render without `framer.css`.

---

## What shipped

### `frontend/styles/app.css` — 222 lines, aliasing Framer's tokens

```css
--bg:          var(--token-cef4d4a6-…, #0c0f16)   /* page ground        */
--bg-elevated: var(--token-f8eb999f-…, #06070a)   /* card background    */
--accent:      var(--token-991642a5-…, #0175ff)   /* brand blue         */
--border:      var(--token-f4dc11a3-…, #7da4ff29) /* the hairline       */
--amber:       var(--token-40eb5c15-…, #ffcd7d)
--text-muted:  var(--token-e77749d5-…, #9ba9c4)
```

Three specific corrections after the first attempt:

| | Wrong | Right |
|---|---|---|
| Display font | Edgar Sigma (blocky) | **BentonSansRE, Verdana** at 34px/400 |
| Nav | flat bar, bottom border | **floating pill**, `blur(8px)`, radius 999px, inset highlight instead of a border |
| Primary button | flat white | the landing's **glow**: 5-layer drop shadow + two inset glows, blue from one corner and amber from the other |

Card radius is 12px — the landing's dominant value (48 uses), not the 24px I
first guessed.

`--glow-primary` and `--glass-inset` are lifted verbatim from the landing's
Get Started CTA and nav pill, so app buttons and the app nav are the same
objects rather than approximations.

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

## Landing link cleanup

The Framer template shipped 19 internal links to pages that do not exist and 6
external links belonging to someone else. Every "Get Started" CTA (8 of them,
across Nav, Hero, Footer, Exceptionalities, Integration and Pricing) pointed at
`./pricing`, `./contact` or `./integration`.

After: the landing has **five destinations, all real**.

```
/                                     home
/app                              9x  the app
/app/compare                          "See Situations"
github.com/austinjeremiah/Memora  4x  Contact, Build Log, About
sepolia.basescan.org/address/0xc54…   "View on Basescan" — the live contract
```

Plus in-page anchors `#platform`, `#how-it-works`, `#pricing`, each verified to
exist as a section id.

**Removed outright:** 9 footer blocks with no possible destination (Changelog,
Privacy policy, Terms, "Launching Soon…", a `./404` link) including **four
social links belonging to the template's author**. Two components deleted:
`BuyNowBadge.tsx`, which carried the template seller's **LemonSqueezy checkout
link**, and `FramerBadge.tsx`.

A note for anyone debugging this later: the CTA fix looked broken for a while
because two stale `next-server` processes were serving a pre-fix build. The
source was correct throughout. `pkill -f next-server` before concluding a
frontend change did not apply.

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
