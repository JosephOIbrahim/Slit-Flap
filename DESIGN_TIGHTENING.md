# DESIGN TIGHTENING PASS — Pentagram Principles Applied

## Context

You are refining the frontend of DEPARTURES, a split-flap departure board project manager. The design elements are correct — split-flap character modules, dark panels, amber accent, Disket Mono display font, JetBrains Mono system font, flip animations, session pulse, NEXT UP, daily recap. **Don't change what's there. Tighten how it's executed.**

This is a production-hardening pass through the lens of Pentagram studio's design philosophy. Read every principle below. Apply each one to the existing codebase. The result should feel like the same board, but with every detail considered and resolved.

---

## The Seven Principles

### 1. EVERY ELEMENT EARNS ITS SPACE

Pentagram never adds something because they can. Every element on screen must answer: **"What does this communicate that nothing else already communicates?"**

**Audit the board for redundancy:**
- If track number AND domain AND status are all visible, does the user need all three simultaneously? Or can one be contextual (appears on hover/expand)?
- If the session pulse dot AND the session time are both showing, does the dot add information the number doesn't? If not, the dot alone is enough — the number appears on hover.
- If the NEXT UP label AND the amber border are both present, choose one. The border IS the label. Words that restate what visual treatment already says are noise.
- The filter bar count (e.g., "15") — does anyone use this? If not, remove it. If yes, make it whisper harder.

**Action:** Walk every visible element. If removing it loses zero information, remove it. If two elements say the same thing, kill the weaker one.

---

### 2. TYPOGRAPHY HAS ONLY TWO VOLUMES: SHOUT AND WHISPER

Pentagram's best work uses extreme contrast. The headline is massive. The caption is tiny. There is no middle. The middle is where design goes to feel "fine" instead of "intentional."

**Audit for middle-volume text:**
- Project names (Disket Mono split-flap) = SHOUT. This is correct. Don't touch.
- System text (JetBrains Mono 7-9px) = WHISPER. This is correct. Don't touch.
- Anything between 10-20px that isn't the header clock = suspected middle. Examine each. Is it a shout or a whisper? Pick one. No font size between 10px and the project name size should exist unless it's the header title or clock.

**Specific checks:**
- Event row names at 13px — is this a shout or a whisper? It's neither. Make it a whisper (10px) or give it its own display treatment. Don't let it float in the middle.
- Status word size — should it be the same 8px as domain/track, or does status deserve to be louder? Decide. Don't split the difference.

---

### 3. ONE GRID. EVERYTHING ON IT.

Pentagram aligns obsessively. If the left edge of a project name is at 24px, then the left edge of EVERY piece of content is at 24px or at a deliberate, measured offset from it.

**Audit alignment:**
- The main content padding is 24px. Is every element's left edge at exactly 24px? Or do some elements (edit panel inputs, log entries, email rows) drift by 1-4px? Normalize.
- Vertical rhythm: is the space between the top whisper line, the name, and the bottom whisper line mathematically consistent across every panel? Or does it vary by project name length? It should be fixed. The name truncates; the rhythm doesn't flex.
- The 18px gutter between panels — is this the SAME unit used anywhere else? Pentagram uses a spatial scale. If 18px is the gutter, then padding should relate to it: 18, 24 (18×1.33), 36 (18×2), etc. Audit all spacing values against a base unit.

**Action:** Define a spacing scale (e.g., 4, 8, 12, 18, 24, 36, 48) and force every padding, margin, and gap to snap to this scale. No arbitrary values.

---

### 4. COLOR IS INFORMATION, NOT DECORATION

One accent color: amber `#d4a012`. This is correct. But audit how it's used.

**The rule:** Amber means "this needs your attention right now." If amber appears on something that doesn't need attention, it dilutes the signal.

**Audit amber usage:**
- Clock (header) — does the time need your attention? Not usually. The clock should be `#666` or lighter. Amber is wasted here.
- NEXT UP border — YES. This needs your attention. Amber is correct.
- ACTIVE/ROLLING status — YES. These are live. Amber is correct.
- Time on events/projects — does the time slot need attention? Or is it just metadata? If it's metadata, it should be grey. If it's "this is happening soon," amber might be earned.
- Interval selector — the selected interval lit up in amber. Does this need attention? No. It's a setting. Grey with a subtle indicator.

**Action:** Amber should appear in fewer than 5 places on any given screen. If it appears in more, some uses are decorative and should revert to grey.

---

### 5. MOTION IS PUNCTUATION, NOT PROSE

Pentagram uses motion sparingly. A single transition says "something changed." Constant animation says "I'm a tech demo."

**Audit motion:**
- The arrival cascade (rotateX flip on filter change) — this is punctuation. Good. Keep it.
- Character-by-character flip on expand/status change — this is punctuation. Good.
- Hover scale+lift on panels — is this punctuation or fidgeting? On desktop, it communicates "this is interactive." On mobile, it doesn't exist. Does it need to be this dramatic? `scale(1.015)` with a 40px shadow might be over-performing. Try `scale(1.005)` with a 20px shadow. Subtler. More confident.
- Session pulse dot color transition (2s ease) — this is atmosphere, not information. It could be instant and lose nothing.

**Action:** Reduce every animation duration by 20%. If it still communicates, reduce again. Stop when meaning is lost.

---

### 6. THE EMPTY STATE IS A DESIGN

Pentagram designs the blank page as carefully as the full page. What does the board look like with 0 projects? With 1? With 50?

**Audit states:**
- 0 projects: "NO ACTIVE DEPARTURES" — is this typographically resolved? Same care as a full board?
- 1 project: does a single panel feel intentional, or does it feel like something broke?
- The "No time blocked" section label — is its vertical spacing consistent with the panels above it?
- Loading state: "LOADING" — should this have a split-flap animation? Or is static text more Pentagram (confident, unhurried)?

**Action:** Screenshot each state. If any feels unfinished, resolve it with the same level of detail as the primary view.

---

### 7. THE DETAILS YOU DON'T NOTICE ARE THE ONES THAT MATTER MOST

This is the final pass. The things no one will consciously see but everyone will feel.

**Checklist:**
- **Touch targets:** Every tappable element on mobile is minimum 44×44px. Audit the status word, the flip icon, the filter buttons. If they're smaller, wrap them in a larger hit area.
- **Text rendering:** `-webkit-font-smoothing: antialiased` on body. `text-rendering: optimizeLegibility` on display text. If not already present, add.
- **Color consistency:** Every grey in the system should come from a defined palette, not ad-hoc hex values. How many distinct greys exist? If more than 6, consolidate. Pentagram uses 3-4 greys maximum.
- **Border radius:** The panels use 6px. Is this the ONLY border radius in the system? If buttons use a different radius, normalize. One radius or zero. Not two.
- **Opacity vs color:** Some shipped states use `opacity: 0.3`. Others use grey colors. Pick one method. Opacity is cheaper but affects child elements. Grey colors are precise. Choose and apply consistently.
- **Focus states:** Tab through the interface. Do focused elements have a visible indicator? Amber outline on focus. Not default blue.
- **Scrollbar:** On webkit, the scrollbar should be near-invisible: `8px wide, #1a1a1a thumb, transparent track`. It shouldn't compete with the content.

---

## How to Execute

1. Read the full `frontend/src/App.jsx`
2. Walk each principle. Make a list of every change needed.
3. Present the list BEFORE making changes. Get approval.
4. Execute all changes in a single coherent pass. Don't interleave with other work.
5. Test: does the board still feel like a Solari departure board? Does it feel tighter? If you removed something and the board feels emptier rather than more focused, put it back.

## The Test

When the pass is done, show the board to someone and ask: "What do you notice?" If they say "the typography" or "the animation" — something is still competing for attention. If they say "where my projects are" — you succeeded. The design disappeared. The information remained.

---

*"Simplicity is not the goal. It is the by-product of a good idea and modest expectations." — Paul Rand*

*"Make it simple, but significant." — Don Draper (but Pentagram would actually agree)*
