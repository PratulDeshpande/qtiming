---
name: qtiming documentation
description: "The Datasheet: a white, ruled, one-blue documentation theme where every claim reads as a numbered row with its condition and its source."
colors:
  paper: "#FFFFFF"
  ink: "#111418"
  muted: "#4A5563"
  rule: "#D9DEE4"
  wash: "#F4F6F9"
  datasheet-blue: "#0B5FA5"
  blue-tint: "#EAF2FA"
  selection: "#CFE3F5"
  guide-grey: "#8892A0"
typography:
  display:
    fontFamily: "B612, system-ui, sans-serif"
    fontSize: "2.1rem"
    fontWeight: 700
    lineHeight: 1.14
    letterSpacing: "-0.012em"
  headline:
    fontFamily: "B612, system-ui, sans-serif"
    fontSize: "1.18rem"
    fontWeight: 700
    lineHeight: 1.3
  title:
    fontFamily: "B612, system-ui, sans-serif"
    fontSize: "0.98rem"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "B612, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.14em"
  table-head:
    fontFamily: "B612, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.07em"
  ui:
    fontFamily: "B612, system-ui, sans-serif"
    fontSize: "0.86rem"
    fontWeight: 400
    lineHeight: 1.4
  code:
    fontFamily: "Source Code Pro, ui-monospace, Consolas, monospace"
    fontSize: "0.82rem"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  none: "0"
spacing:
  strip-height: "56px"
  rail-width: "248px"
  margin-width: "288px"
  measure: "37rem"
  main-pad-x: "56px"
  main-pad-top: "40px"
  strip-pad-x: "32px"
  cell-pad: "0.5rem 0.8rem"
components:
  strip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    height: "{spacing.strip-height}"
    padding: "0 32px"
  search-input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    height: "34px"
    width: "260px"
    typography: "{typography.ui}"
  table-head:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    typography: "{typography.table-head}"
    padding: "{spacing.cell-pad}"
  code-block:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.none}"
    padding: "1rem 1.1rem"
  admonition-title:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "0.35rem 0.85rem"
  nav-link-active:
    textColor: "{colors.datasheet-blue}"
  nav-link-hover:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
---

# Design System: qtiming documentation

## Overview

**Creative North Star: "The Datasheet"**

The documentation is set as the part datasheet a hardware engineer already trusts. A claim is a row with its condition and its source; limits are stated as plainly as results. The page is white, the ink is near-black, hairline rules do the work that cards and fills do elsewhere, and a single blue marks what can be followed or measured. It is read at a desk, closer to a printed spec than to a product site, so density is calm and the reading column is narrow.

The world is recognisable with the words removed: a 2px ruled header strip carrying a document number (`QT-<version> · alpha · <build date>`), a left index rail, a 37rem text column, and numbered Notes in the right margin that come from markdown footnotes. Timing-diagram figures are drawn in inline SVG in the margin (Fig. 1 on the home page, Fig. 2 on the verdicts page) and are the one place the system moves.

Rejected on purpose: kicker lines above headings, coloured side-stripes, cards, decorative gradients, section numbers, and icon glyphs. Light only, by design: this is a printed-datasheet world read at a desk, and no dark scheme exists (`color-scheme: light`).

**Key Characteristics:**
- White page, near-black ink, one blue (`datasheet-blue`), hairline `rule` borders, no radius anywhere.
- State is carried by text, weight and rules (bold, underline, ink hairlines above and below), never by hue alone.
- Three type voices: B612 for structure, Source Serif 4 for prose, Source Code Pro for code and values.
- A fixed 37rem measure for prose; code blocks and tables use the full reading column.
- A print stylesheet drops chrome and prints the column as a plain document.

## Colors

Monochrome ink on paper with exactly one chromatic colour.

### Primary
- **Datasheet Blue** (`#0B5FA5`): links, the active page in the rail and "On this page" list, the document number in the strip, dimension lines and their labels in figures, the caret, the focus ring, heading anchors, search result titles. Nothing else is chromatic.

### Neutral
- **Paper** (`#FFFFFF`): page and input background.
- **Near-Black Ink** (`#111418`): body text, headings, the 2px strip rule, and the 1px ink rules under h2, above Notes and the pager, around admonitions and the search results panel.
- **Slate Muted** (`#4A5563`): secondary text, tracked small-caps group labels, Notes text, captions, the footer.
- **Hairline Grey** (`#D9DEE4`): cell borders, code block borders, rail edge, `hr`, result separators.
- **Cool Wash** (`#F4F6F9`): table heads, code blocks, admonition titles, nav hover.
- **Blue Tint** (`#EAF2FA`): the hovered or selected search result only.
- **Selection Blue** (`#CFE3F5`): text selection.
- **Guide Grey** (`#8892A0`): dashed guide lines in figures.

### Named Rules
**The One Blue Rule.** Blue means "follow this", "you are here", or "this is a dimension". It is never used to signal status, and it is never the only carrier of meaning: the active page is also bold and ruled, links are also underlined.

**The Text-Carries-State Rule.** Verdicts and states are written (PROVED, PROVED-UNDER, REFUTED, UNKNOWN) and set in weight or case. No red/green status colours exist in the system.

## Typography

**Display / Heading / Label / Table Font:** B612 (400, 700) with system-ui, sans-serif
**Body Font:** Source Serif 4 (400, 600, 400 italic) with Georgia, serif
**Code Font:** Source Code Pro (400) with ui-monospace, Consolas, monospace

**Character:** an aviation-cockpit sans for structure against a book serif for reading, with a plain monospace for identifiers. All three are self-hosted woff2 with their OFL licences beside them in `docs-theme/fonts/`.

### Hierarchy
- **Display** (700, 2.1rem, 1.14, -0.012em; 1.75rem below 900px): page title (h1), balanced wrap.
- **Headline** (700, 1.18rem, 1.3): h2, with a 1px ink rule beneath and 2.8rem above.
- **Title** (700, 0.98rem, 1.35): h3. h4 is 0.85rem bold, +0.02em.
- **Body** (400, 1.0625rem, 1.65, lining numerals): prose, at a fixed 37rem measure.
- **Label** (700, 0.75rem, 0.14em tracking, uppercase, `muted`): rail group titles, "On this page", "Notes", pager "Previous/Next" (400), admonition titles (0.12em).
- **Table head** (700, 0.75rem, 0.07em, uppercase) over table body in B612 0.88rem with tabular numerals.
- **Code** (400, 0.82rem/1.6 in blocks, 0.86em inline): `pre`, inline `code`, the strip's document number (0.75rem), figure labels (11px in SVG).

### Named Rules
**The Fixed Measure Rule.** Prose width is `37rem`, not `ch`, because `ch` widens on large headings and drifts the column. Paragraphs, lists, headings and admonitions take the measure; code blocks and tables take the whole reading column.

**The Source Code Pro Rule.** Code is Source Code Pro, not B612 Mono. B612 Mono sets the period flush-left in a wide cell, so `ff.default` reads as "ff. default". Source Code Pro is also the same foundry as the body face.

**The 12px Floor Rule.** No functional text is below 12px (0.75rem). Labels once at 10.56px were raised to this floor. The only sub-12px type is the superscript footnote mark (0.72em of its line).

## Layout

A three-column shell centred to 1440px: index rail `248px`, reading column (flexible, padding `40px 56px 72px`), margin `288px`. Above 1180px all three show. From 900 to 1180px the margin column is dropped; the figure (home) moves into the text as a 20rem inline figure and "On this page" becomes a ruled disclosure at the top of the article. Below 900px the shell is a single block: the rail is replaced by a "Menu" disclosure under the strip, the strip hides the tagline, document number and Source link, and the page padding drops to `28px 20px 56px`.

The header strip is sticky, `56px` tall, with a 2px ink bottom rule; anchors scroll with `strip + 20px` of padding. The rail is sticky and scrolls on its own. The margin's contents (figure on home, "On this page" and Notes elsewhere) are sticky. Rhythm is rem-based: paragraphs 1.05rem apart, h2 2.8rem above, h3 2rem above, tables and code 1.3 to 1.4rem around.

Print: strip, rail, margin, menus, pager and copy buttons are removed; the column prints full width with ink-coloured, un-underlined links and wrapped code.

## Elevation & Depth

Flat. There are no drop shadows anywhere; depth is conveyed by hairline rules and the tonal `wash`. The search results panel is separated by a 1px ink border, not by a shadow. The only gradients are functional scroll-shadow cues on overflowing code blocks and tables (a 0.7rem fade at the clipped edge, masked by a local cover), which appear only while content is scrollable and are not decoration.

### Named Rules
**The Rules-Not-Shadows Rule.** Separate with a 1px or 2px line, or the `wash` tone. A shadow is never the answer.

## Shapes

Square. Every border radius is 0: inputs, code blocks, buttons, admonitions, results. The form language is the ruled box and the horizontal line: ink rules (strong) for structure and headings, hairline grey for cells and dividers. Active navigation is not a filled pill but a link bracketed by 1px ink lines above and below.

## Components

### Header strip
A single 56px row: `qtiming` in B612 700 (the wordmark is plain text, no logo), the tagline in muted 0.8rem, the search field pushed right, the document number in blue Source Code Pro (`QT-<version> · alpha · <yyyy-mm-dd>`), then a bold "Source" link. A 2px ink rule underlines it.

### Index rail
B612 0.86rem links in groups headed by tracked small-caps labels (nested groups use bold 0.8rem sentence case). Hover tints `wash`. The current page is blue, bold and bracketed by 1px ink lines.

### Search
A 260px, 34px-tall square field with a 1px ink border and 0.85rem B612 text. Results open in a 1px ink panel (max 62vh) with blue bold titles over muted serif excerpts; the hovered or selected result takes `blue-tint`.

### Tables
Hairline-ruled grid with `wash` heads set in tracked small caps and a 1px ink rule under the head. Tabular numerals; code in cells never wraps. Wide tables scroll horizontally inside a wrapper with edge shadows.

### Code blocks
`wash` ground, 1px hairline border, no radius, Source Code Pro 0.82rem. A "COPY" button (small tracked caps, hairline border) appears on hover or focus, and always on touch devices.

### Admonitions
A 1px ink box with a `wash` title bar in tracked small caps, serif 0.95rem content. No side stripe, no icon, no colour by type.

### Notes
Footnotes in markdown become numbered Notes: on wide screens `qt.js` moves them into the right margin under a 1px ink rule and "Notes" label; where there is no margin they stay as a "Notes" block at the end of the article. The reference mark is a bold, un-underlined superscript.

### Timing figures (signature)
Inline SVG waveforms: ink 1.6px square-cornered traces, dashed grey guides, blue 1.4px dimension lines with blue Source Code Pro labels, and an uppercase signal label at left. Fig. 1 is sticky in the home margin; Fig. 2 sits above "On this page" on the verdicts page. Captions are muted 0.8rem with a bold "Fig. n." lead-in. Each figure draws in once (1.1s, `cubic-bezier(0.16,1,0.3,1)`, second trace delayed 0.45s) and only when `prefers-reduced-motion: no-preference`; otherwise it is static.

### Pager and footer
A 1px ink rule over two columns (Previous / Next), small tracked caps labels over a bold title; hover turns the title blue. The footer is a hairline-topped row of 0.76rem muted metadata.

## Do's and Don'ts

### Do:
- **Do** use `datasheet-blue` only for links, the current location, dimensions and focus.
- **Do** carry state in words, weight and rules so it survives greyscale and print.
- **Do** keep prose at `37rem` and give code and tables the full column.
- **Do** keep every functional label at 12px or larger.
- **Do** write code, flags and values in Source Code Pro and tables, labels and headings in B612.
- **Do** gate any animation behind `prefers-reduced-motion: no-preference`.

### Don't:
- **Don't** add kicker or eyebrow lines above headings, section numbers, or icon glyphs.
- **Don't** add coloured side-stripes, cards, decorative gradients, or drop shadows.
- **Don't** round corners.
- **Don't** introduce a second chromatic colour or red/green status colours.
- **Don't** use B612 Mono for code, or set measure in `ch`.
- **Don't** add a dark mode: the world is a printed datasheet read at a desk.
