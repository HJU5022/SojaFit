# SojaFit design

Single source of truth for how the SojaFit frontend looks. Code follows this file; if the code
needs something this file does not allow, change this file first and say why. Product intent
lives in `SPEC.md` at the repository root; this file only fixes the visual system.

## 1. Direction

- **One reference: Linear's product UI.** A dark-grey workbench: a content panel floating on a
  slightly darker ground, hairline borders, dense 13px text, no decoration. Colour temperature
  and card softness follow Claude Code's desktop app; table and divider crispness follow Codex.
- What we take from it: density, the two-level ground, hairlines, quiet neutral controls.
- What we do not take: its brand purple, its marketing gradients, its issue-tracker vocabulary.
- The workbench uses a **conversation with selectable part details**: concise summaries and
  part links in the conversation; the selected part's verdict, checks and evidence in the
  properties panel. The landing page retains its review-document example.
- Conversation messages use neutral bubbles: user on the right, AI on the left, with no
  avatars, names or question headers. Keep long text left-aligned inside each bubble;
  user bubbles use `--surface`, AI bubbles use `--hover` and a hairline border.
- Owner's words: orderly, efficient, readable, premium, not flashy. Layout and emphasis matter most.

## 2. Colour

Rule: **neutrals are for structure and controls; the five verdict colours are only for results the
server sent.** A verdict colour never appears on a button, link, focus ring or decoration.

| Token | Value | Use |
|---|---|---|
| `--side` | `#1f1e1d` | App ground, rail |
| `--bg` | `#262624` | Content panel |
| `--surface` | `#30302e` | Dialogs, menus (raised) |
| `--hover` | `rgb(255 250 240 / 0.06)` | Hover, input fill, chips |
| `--line` | `rgb(255 250 240 / 0.09)` | Hairline dividers |
| `--line-2` | `rgb(255 250 240 / 0.17)` | Control borders |
| `--ink` | `#f5f4ef` | Titles, values that matter |
| `--ink-2` | `#d1cfc5` | Body |
| `--ink-3` | `#a6a399` | Labels, meta, placeholders |
| `--ink-4` | `#918e85` | Disabled text, separators only |
| `--accent` | `#ece9e1` | Primary button fill, focus ring |
| `--wire` | `#7d7a72` | Diagram wires (non-text mark) |

Verdicts (fixed wording, fixed colour, always with a dot **and** the text label):

| Verdict | Label | Token | Value |
|---|---|---|---|
| `IDENTICAL` | 동일품 | `--identical` | `#68c99a` |
| `SPEC_EQUIVALENT` | 사양 동등 | `--equivalent` | `#63c5d0` |
| `ROLE_SUFFICIENT` | 역할상 충분 | `--sufficient` | `#8aaaff` |
| `NOT_SUFFICIENT` | 불충족 | `--insufficient` | `#f18383` |
| `NOT_VERIFIED` | 문서로 확인 안 됨 | `--unverified` | `#e4c36a` |

Measured contrast on `--bg` (WCAG): ink 13.8, ink-2 9.7, ink-3 6.0, ink-4 4.6, verdicts 6.0-8.9,
wire 3.5. On `--surface`, ink-4 is 4.0, so **ink-4 is never used for readable text on `--surface`.**
Text needs 4.5:1; non-text marks (wires, borders that carry meaning) need 3:1.

Deliberate exceptions to the anti-default list, with reasons:
- Warm dark-grey ground: the owner rejected pure black (`#08090a`) and then cool grey (`#1d1e22`,
  "too dark, no point of colour"). Neutrals are warm-tinted at the brightness of Claude Code's
  desktop app; its orange accent is not used because it sits between the 불충족 red and the
  문서로 확인 안 됨 yellow.
- The point of colour is the verdict: the document head carries the verdict tone as an 8% fill
  with a 24% border (`color-mix`). No other surface is tinted.
- No brand hue: the only saturated colours on screen are verdicts, so a verdict is never mistaken
  for chrome. Do not add an accent colour.

## 3. Type

Font: `Pretendard Variable` (Korean UI text; its Latin is Inter-based, accepted because the
reference is Linear). No second typeface. No monospace labels.

| Role | Size / line | Weight |
|---|---|---|
| Page title, verdict | 22 / 30 | 590 |
| Document title | 18 / 26 | 590 |
| Section heading, lead | 14 / 22 | 590 (lead 510) |
| Body, table cells | 13 / 20 | 510 |
| Label, meta, table head | 12 / 18 | 510 |
| Diagram annotations only | 11 | 510 |

Landing only (a page that is read, not worked in): display 40 / 48 at 590, section title 28 / 36
at 590, body 16 / 26 at 510, supporting text 14 / 22. Product fragments shown on the landing keep
the workbench sizes. At <= 820px display drops to 28 / 36.

- Only these sizes. Emphasis comes from `--ink` vs `--ink-3` and 590 vs 510, not from new sizes.
- Numbers: `tabular-nums`; numeric columns right-aligned; unit follows the value.
- Korean: `word-break: keep-all`. Headings may use `letter-spacing: -0.012em`; body none.
- On screens <= 820px every `input`, `textarea`, `select` is 16px (prevents iOS zoom).

## 4. Space and shape

- Spacing scale: **4, 8, 12, 16, 20, 24, 32, 40, 48**. Two micro-steps are allowed: 2px (gap
  between stacked rail rows) and 6px (icon-to-label gap inside one control). Nothing else:
  no 3, 7, 10, 14, 19.
- One page inset: `--inset` 24px (16px <= 820px). Rail, bar, document and properties column all
  start on it.
- Large button (`.btn-large`, landing and login only): 40px high, 44px <= 820px.
- Landing: max width 1080px, sections separated by a hairline and 48px, numbered in order.
- Charts are hand-drawn SVG/CSS in neutrals (`--accent` for our value, `--ink-4` for others).
  Verdict colours are never used in charts.
- Row height: `--row` 28px for rail rows, buttons, property rows; 40px for table body rows; 32px
  for text inputs; 44px minimum touch target <= 820px.
- Radius: 4 (chips), 6 (controls, tables, cards), 8 (composer, menus), 10 (messages, app panel, dialogs).
- Borders 1px. Elevation only on things that float (menu, dialog): one soft shadow, no glow.
- Layout: rail 224px, document max 880px centred, properties column 280px, lists max 960px.
- SVG diagrams render at natural size, 1px strokes on half-pixel coordinates with
  `shape-rendering: crispEdges`. Never scale them with CSS.

## 5. Components and states

Every interactive element defines: default, hover, active, focus-visible, disabled. Every data
view defines: loading (skeleton, not spinner-only), empty (one sentence plus the next action),
error (`role="alert"`, what failed plus retry), and the real content.

- Buttons: neutral outline by default; one primary (light fill, dark text) per view at most.
- Focus: 2px `--accent` outline, offset 3px, always visible for keyboard.
- Icons: `lucide-react`, 15px at stroke 1.75 (13-14px inside dense rows). An icon set is all or
  nothing within one list: either every row has one or none does.
- Brand: the approved grid S symbol from `new_logo.png`, with transparent ground and the
  existing accent/ink-2/ink-3 neutrals. Show it at 22-24px beside the `SojaFit` link text;
  do not clip its cells with a rounded image container.
- Tables <= 820px become stacked cards with `data-label`; no horizontal page scroll at 390px.
- Before the first question a review shows only its title and composer (`review-idle`); circuit,
  checks and properties appear once a review starts.
- Every result shows "같은 동작은 보장하지 않습니다".
- Keep the review composer in a separate bottom row while the conversation scrolls.
  Show a down-arrow button above it when the conversation end is below the visible area;
  jump only when requested, preserving the draft and attachments.
- In the properties panel, compare each condition's required and candidate values side by side.
  Keep the condition code and result visible; reveal basis, test conditions and citation under
  a native disclosure. Keep failure/uncertainty reasons and candidate cautions visible when collapsed.
  Use hairline row separators and the existing type/spacing scale instead of tall stacked cards.
- File dragging uses a neutral dashed overlay with no pointer capture or animation.
  Keep attachment chips below the composer, scroll the list above 120px, and show pending
  transfer availability beside the files.

## 6. Motion

Only state changes move: hover/press 120ms, dialog reveal 140ms `cubic-bezier(0.16, 1, 0.3, 1)`,
run progress indicator. No entrance choreography, no scroll effects in the workbench.
`prefers-reduced-motion` removes all of it.

## 7. Interaction floor

Enter submits (not while composing Hangul; Shift+Enter is a newline), Esc and outside click close
dialogs and menus, focus returns to the trigger, destructive actions need a second confirm,
colour is never the only signal.

## 8. Never

- Verdict logic in the frontend. The screen renders server DTOs only.
- Decorative gradients, glassmorphism, glows, emoji, unicode glyphs as icons.
- Middle-dot meta chains (`A · B · C`) as a layout device; use separate labelled fields.
- Mono uppercase eyebrow labels, pill badges for everything, cards inside cards.
- A new colour, size, radius or spacing value that is not in this file.
- Invented data: timestamps, counts, customer names, claims.

## 9. Check before calling a screen done

1. Captures at 390, 768 and 1440 wide; no horizontal scroll at 390.
2. Every value in the CSS is a token or on a scale above.
3. Text contrast >= 4.5:1, focus visible on every control, all states from section 5 exist.
4. `tsc -b`, tests and build pass.
