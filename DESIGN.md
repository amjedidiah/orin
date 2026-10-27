---
name: Orin
description: The switchboard. Ask once; see which line your ask was put through to, and why.
colors:
  cord-red: "#a62a21"
  cord-red-night: "#c3352b"
  signal-amber: "#f0a500"
  signal-amber-night: "#ffb627"
  focus-amber: "#b06f00"
  brass: "#b48a45"
  brass-night: "#c19a5b"
  brass-ink: "#1d150a"
  brass-off: "#4b443a"
  brass-off-ink: "#d6cdbd"
  bakelite: "#25211b"
  bakelite-rule: "#3b362d"
  socket-hole: "#0c0a08"
  socket-rim: "#4a4237"
  desk: "#cfc8bb"
  desk-raised: "#e2ddd3"
  desk-rule: "#b3ab9c"
  desk-night: "#1a1713"
  ivory-slip: "#fffdf8"
  ivory-slip-night: "#f3ecdd"
  slip-rule: "#e3dccd"
  ink: "#1e1b16"
  ink-dim: "#4f483d"
  slip-dim: "#5c5447"
  night-text: "#efe9dd"
  night-text-dim: "#b9b0a0"
  error-red: "#9e2318"
  error-red-night: "#ff8a7a"
typography:
  plate-display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.9rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.14em"
  plate-title:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 600
    letterSpacing: "0.06em"
  plate-name:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "0.08em"
  plate-label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 600
    letterSpacing: "0.1em"
    fontFeature: "tnum"
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  operator-note:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
rounded:
  tag: "2px"
  plate: "3px"
  slip: "4px"
  field: "6px"
  lamp: "50%"
spacing:
  xs: "0.45rem"
  sm: "0.6rem"
  md: "0.9rem"
  lg: "1.25rem"
  xl: "2rem"
components:
  button-send:
    backgroundColor: "{colors.signal-amber}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lamp}"
    size: "3rem"
  button-plug-in:
    backgroundColor: "{colors.signal-amber}"
    textColor: "{colors.ink}"
    rounded: "{rounded.slip}"
    typography: "{typography.plate-name}"
    height: "2.75rem"
    padding: "0 1.25rem"
  jack-plate:
    backgroundColor: "{colors.brass-night}"
    textColor: "{colors.brass-ink}"
    rounded: "{rounded.plate}"
    typography: "{typography.plate-name}"
    padding: "0.4rem 0.7rem 0.45rem"
  jack-plate-unavailable:
    backgroundColor: "{colors.brass-off}"
    textColor: "{colors.brass-off-ink}"
    rounded: "{rounded.plate}"
  answer-slip:
    backgroundColor: "{colors.ivory-slip}"
    textColor: "{colors.ink}"
    rounded: "{rounded.slip}"
    padding: "0.95rem 1.25rem 1.15rem"
  ask-slip:
    backgroundColor: "{colors.desk-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "0.7rem 1rem 0.8rem"
  free-tag:
    textColor: "{colors.ink}"
    rounded: "{rounded.tag}"
    typography: "{typography.plate-label}"
    padding: "0 0.45rem"
  line-key-field:
    backgroundColor: "{colors.desk-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "0.75rem 1rem"
---

# Design System: Orin

## Overview

**Creative North Star: "The Switchboard":**

Orin is the operator, and the screen is its board.
Every ask comes in on your line; the board shows which jack it was put through to and why.
The world is a working telephone exchange, not a chat app: a Bakelite panel with brass jack plates, amber lamps, ivory call slips and one red patch cord that ties each answer to the line that served it.
It deliberately refuses the centred chat thread with a history sidebar.

It is an Operate surface used in short bursts on phone and desktop, so the metaphor lives in precise details rather than decoration.
The cord, the lamps and the plates all carry real state: which model is answering, which are available, which one served for free, and when a fallback re-patched the call.
Nothing on the board is ornamental; if a physical part doesn't encode routing truth, it isn't there.

Day board (light) is the default and night board (dark) follows the system setting.
The jack field is Bakelite in both: only the desk around it changes.

**Key Characteristics:**

- Bakelite jack field on the left (a lamp strip across the top on phones), call log on the right, line key docked at the bottom.
- Engraved condensed caps for anything that is a plate, label or number; a plain humanist sans for everything you read.
- One red cord, drawn live from the newest slip's plug to the answering jack.
- Lamps report availability: lit amber is available, dark is unavailable with the reason beside it.
- Routing is always visible: target, reason, alternatives, steps, re-patches, who served it, and whether it was free.

## Colors

A warm, low-saturation exchange palette (Bakelite browns, brass, ivory) with two signal colours that carry meaning: amber for "live/available/act" and red for "the cord".

### Primary

- **Cord Red** (`cord-red`, night `cord-red-night`): the patch cord, the plug icon, re-patch and disclosure chevrons, links in answers. It always means "this is the connection".

### Secondary

- **Signal Amber** (`signal-amber`, night `signal-amber-night`): lit lamps, the send and plug-in buttons, text selection. It means "live" or "act now".
- **Focus Amber** (`focus-amber`): the keyboard focus ring and caret on the day board (night board uses Signal Amber).

### Tertiary

- **Brass** (`brass`, `brass-night`) with **Brass Ink** (`brass-ink`): nameplate and jack plates. **Spent Brass** (`brass-off`, `brass-off-ink`) marks an unavailable jack.

### Neutral

- **Bakelite** (`bakelite`, `bakelite-rule`): the jack field in both themes, dotted with the empty holes of unused jacks. **Socket Hole** / **Socket Rim** (`socket-hole`, `socket-rim`) for the jack sockets.
- **Desk** (`desk`, `desk-raised`, `desk-rule`; night `desk-night`): the call-log background, ask slips and the line key field.
- **Ivory Slip** (`ivory-slip`, night `ivory-slip-night`) with **Ink** (`ink`, `slip-dim`, `slip-rule`): answer slips stay light in both themes, like paper on a dark desk.
- **Night Text** (`night-text`, `night-text-dim`): text on the jack field and the night desk.
- **Error Red** (`error-red`, night `error-red-night`): dropped lines and rejected keys. On ivory slips it is always the day value.

### Named Rules

**The Meaningful Colour Rule.** Amber and red are signals, not decoration. Amber appears only where something is live, available or actionable; red only on the cord and things that belong to it.

**The Paper Stays Paper Rule.** Answer slips and the operator-key card are ivory in both themes. Text on them always uses the slip ink tokens, never the night text tokens.

## Typography

**Display Font:** Barlow Condensed (with Arial Narrow, sans-serif)
**Body Font:** Barlow (with system-ui, sans-serif)

**Character:** Barlow Condensed in tracked uppercase reads as engraved plates and stencilled labels; Barlow, from the same family, keeps the reading text calm and plain. Both are SIL OFL, self-hosted via Fontsource.

### Hierarchy

- **Plate Display** (600, 1.9rem, line-height 1, 0.14em, uppercase): the ORIN nameplate only.
- **Plate Title** (600, 1.6rem, 0.06em, uppercase): the quiet-board title and the operator-key title.
- **Plate Name** (600, 1.05rem, 0.08em, uppercase): jack names and the plug-in button.
- **Plate Label** (500–600, 0.75–0.85rem, 0.05–0.1em, uppercase, tabular numerals): call numbers, jack meta, the Free tag, the replay flag.
- **Body** (400, 1rem, 1.55): asks and answers. Answers cap at 70ch.
- **Operator Note** (400 italic, 0.88rem): the route reason under "Put through to". Orin's voice, set apart from the answer.

### Named Rules - Typography

**The Plate Rule.** Condensed caps are for things that would be engraved or stencilled on the board (names, labels, numbers). Never set a sentence the user has to read in them.

## Layout

Two columns on desktop: a jack field of `minmax(14rem, 17rem)` and the exchange taking the rest, full viewport height (`100dvh`) with only the call log scrolling.
Slips cap at 46rem; ask slips sit right (max 36rem), answer slips run the full column.
The call log's left padding (`clamp(2.5rem, 7vw, 6rem)`) leaves room for the cord to hang between the board and the slips, and the line key reuses the same gutters so the composer lines up with the slips above it.

Below 860px the board folds: the jack field becomes a wrapping lamp strip across the top (nameplate word, then lamp + plate per jack; meta, reasons, sockets and the cord are hidden), the call log takes the remaining height, and the line key stays at thumb reach with safe-area padding.
Every jack stays visible on a phone; the strip wraps instead of scrolling.

Rhythm is tight and even: 0.45–0.9rem inside slips and between jacks, 2.25rem between calls.

## Elevation & Depth

Depth is physical and shallow.
Brass plates and the nameplate sit just proud of the panel (`0 1px 2px rgb(0 0 0 / 0.3)`); ivory slips rest on the desk with a soft two-layer paper shadow; sockets are recessed holes.
The cord is the only thing that floats: it draws above everything with its own blurred drop shadow.

### Shadow Vocabulary

- **Plate** (`box-shadow: 0 1px 2px rgb(0 0 0 / 0.3)`): nameplate and jack plates.
- **Slip, day** (`box-shadow: 0 2px 8px rgb(60 48 30 / 0.16), 0 1px 1px rgb(60 48 30 / 0.12)`): answer slips, example prompts, the operator key.
- **Slip, night** (`box-shadow: 0 3px 10px rgb(0 0 0 / 0.45), 0 1px 2px rgb(0 0 0 / 0.4)`): the same, on the night desk.
- **Lamp glow** (`box-shadow: 0 1px 8px` amber at 60%): lit lamps only.
- **Button lift** (`box-shadow: 0 2px 6px rgb(0 0 0 / 0.25)`): send and plug-in.

### Named Rules - Elevation & Depth

**The One Floating Thing Rule.** Only the cord sits above the board. Nothing else gets a large or coloured shadow.

## Shapes

Small, machined corners: 2px for the Free tag and replay flag, 3px for plates, 4px for slips, 6px for ask slips and fields.
Round things are round because they are physical round things: lamps, sockets and the send button.
Disclosure summaries are underlined text with a red chevron, not boxed buttons.
Dashed rules separate the patch header from the answer, like a tear line on a slip.

## Components

### Buttons

- **Send:** a 3rem Signal Amber circle with an ink arrow; lifts 1px on hover; 45% opacity and no shadow when disabled.
- **Plug In** (operator key): the same amber, as a 4px-cornered rectangle in Plate Name caps.
- **Example prompts:** ivory slips on the quiet board; full-width, left-aligned, lift 1px on hover.
- **Focus:** a 2px Focus Amber outline, 2px offset, on every interactive element.

### Jacks (signature)

Lamp, brass plate (name in Plate Name caps, "Free · open weights" or "Paid" in Plate Label caps), socket.
Unavailable jacks go to Spent Brass with a dark lamp and the reason in small italics beneath.
The jack that is answering blinks its lamp in two hard steps (`steps(2)`), like a real board.

### Call slips

- **Ask slip:** desk-raised, right-aligned, with "Call N" in tabular Plate Label caps and the prompt verbatim.
- **Answer slip:** ivory. The patch header reads "Put through to **Model** · host", with a Free tag when a free model served, then the route reason as an Operator Note. After a re-patch the reason is prefixed "Routed to _original_:" so it never seems to describe the fallback model.
- **Alternatives and steps:** a disclosure with alternatives, numbered steps for multi-step routes, and a note when the router fell back to its default line.
- **Re-patch line:** a red repeat icon and "Re-patched from A to B: reason", above the answer it affected.
- **Ringing…:** italic placeholder until the first token or image arrives.

### Free tag

Plate Label caps in a 1px ink outline, 2px corners. Shown only when the model that actually served the step is free.

### The cord (signature)

A cubic curve from the answering jack's socket to the newest slip's plug, sagging more on longer runs. It draws in over 750ms with the house ease-out and seats a plug dot at each end. It redraws on every new call and every re-patch, and tracks layout changes on the board (scroll, resize, a jack plate growing). Hidden on phones; reduced motion shows it fully drawn.

### Line key (composer)

An auto-growing textarea (`field-sizing: content`, up to 40vh) on desk-raised with a 6px corner, next to the send button.

### Operator key (locked board)

A centred ivory card with a key icon in Cord Red, a Plate Title, short copy, a white input and the Plug In button. It scrolls on short screens.

## Do's and Don'ts

### Do

- **Do** route every new state through the board metaphor: lamps for availability, the cord for "who is answering", slips for asks and answers.
- **Do** keep routing visible on every answer: target, reason, alternatives, re-patches, who served it and the Free tag.
- **Do** set plates, labels and numbers in Barlow Condensed caps, and all reading text in Barlow.
- **Do** keep answer slips ivory in both themes and use slip ink tokens on them.
- **Do** honour `prefers-reduced-motion`: the cord appears fully drawn, lamps stop blinking, hover lifts stop.
- **Do** label any made-up data on screen (the dev-only synthetic replay carries a dashed "Synthetic replay" flag).

### Don't

- **Don't** use vendor, Meta, Muse or Llama logos; models are named in plain text only.
- **Don't** use amber or red decoratively; they are signals.
- **Don't** add a second floating element or large coloured shadows; only the cord floats.
- **Don't** fall back to the centred chat thread with a history sidebar.
- **Don't** claim an untested integration works; label it as designed for, not yet tested.
