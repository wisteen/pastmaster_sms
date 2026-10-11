# Design — Virtuakids School Portal

A locked design system for the school portal. Every portal redesign reads this
file before emitting code. Extend this file when the system grows; do not create
page-specific themes.

## Genre

Modern-minimal: calm, precise, and operational. The interface should feel like
a dependable school workbench rather than a marketing dashboard.

## Macrostructure family

- Entry pages: Split Studio — school identity and guidance beside the task.
- App pages: Workbench — a persistent utility rail, compact toolbar, and a wide
  content canvas for tables, forms, reports, and dashboards.
- Content and report pages: Long Document within the Workbench shell — readable
  headings and unboxed content sections, with containment reserved for data.

## Theme

Cool engineered neutrals provide the stable system. Each tenant's existing
primary colour is mapped to the accent role at render time; it must stay below
5% of the viewport. The fallback accent is cobalt.

- `--color-paper`: `oklch(98.5% 0.006 252)`
- `--color-paper-2`: `oklch(96.5% 0.009 252)`
- `--color-paper-3`: `oklch(93.5% 0.012 252)`
- `--color-ink`: `oklch(18% 0.038 252)`
- `--color-ink-2`: `oklch(27% 0.034 252)`
- `--color-rule`: `oklch(88% 0.014 252)`
- `--color-accent`: `oklch(52% 0.19 255)` fallback; tenant-overridable
- `--color-focus`: `oklch(58% 0.2 255)`

## Typography

- Display: Space Grotesk, weight 600, normal style.
- Body: IBM Plex Sans, weight 400.
- Mono: JetBrains Mono, weight 500; reserved for compact metadata and codes.
- Display tracking: `-0.028em`.
- Type scale: major-third-inspired, capped at five visible sizes per screen.

## Spacing

Four-point named scale. Production CSS uses tokens from `tokens.css`; raw
spacing values are not introduced inside components.

## Motion

- State transitions use `--ease-out`, `--ease-in`, and `--ease-in-out`.
- Only transforms and opacity animate.
- App content does not reveal on scroll.
- Reduced motion collapses spatial changes to at most 150 ms.

## Microinteractions stance

- Silent success when the result is already visible.
- Buttons press by one pixel; cards do not lift indiscriminately.
- Hover is paired with focus and click/tap behavior.
- Focus rings appear immediately.
- Hover tooltips delay 800 ms; keyboard-focus tooltips appear immediately.

## CTA voice

- Primary actions: solid tenant accent, 8 px radius, explicit action labels.
- Secondary actions: paper surface, visible border, ink text.
- Destructive actions: restrained red treatment plus text/icon signal.
- Button and input heights share the 44 px touch-target floor.

## Per-page allowances

- Entry pages may use a restrained two-surface composition.
- App pages must not use decorative enrichment; function carries the page.
- Reports and print outputs preserve their document-specific layouts.
- Tenant logos and tenant colours remain authoritative brand inputs.

## What pages MUST share

- School identity treatment and wordmark rhythm.
- Neutral surfaces, typography, focus treatment, and spacing scale.
- Sidebar/topbar geometry and responsive drawer behavior.
- Button, input, table, alert, dropdown, and pagination voice.
- Accent placement below 5% of each viewport.

## What pages MAY differ on

- Dashboard card arrangement according to each role's available data.
- Table density for finance, attendance, and reporting workflows.
- Form width and section composition according to task complexity.
- Status colours when they communicate meaning and include a non-colour cue.

## Exports

### tokens.css

The complete source is [`tokens.css`](tokens.css). Core portable values:

```css
:root {
  --color-paper: oklch(98.5% 0.006 252);
  --color-paper-2: oklch(96.5% 0.009 252);
  --color-paper-3: oklch(93.5% 0.012 252);
  --color-ink: oklch(18% 0.038 252);
  --color-ink-2: oklch(27% 0.034 252);
  --color-rule: oklch(88% 0.014 252);
  --color-accent: oklch(52% 0.19 255);
  --color-accent-ink: oklch(98.5% 0.006 252);
  --color-focus: oklch(58% 0.2 255);
  --font-display: "Space Grotesk", ui-sans-serif, sans-serif;
  --font-body: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --font-outlier: "JetBrains Mono", ui-monospace, monospace;
  --space-3xs: 0.25rem;
  --space-2xs: 0.5rem;
  --space-xs: 0.75rem;
  --space-sm: 1rem;
  --space-md: 1.5rem;
  --space-lg: 2rem;
  --space-xl: 3rem;
  --space-2xl: 4.5rem;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in: cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --radius-card: 0.75rem;
  --radius-input: 0.5rem;
}
```

### Tailwind v4 `@theme`

```css
@theme {
  --color-paper: oklch(98.5% 0.006 252);
  --color-paper-2: oklch(96.5% 0.009 252);
  --color-paper-3: oklch(93.5% 0.012 252);
  --color-ink: oklch(18% 0.038 252);
  --color-ink-2: oklch(27% 0.034 252);
  --color-rule: oklch(88% 0.014 252);
  --color-accent: oklch(52% 0.19 255);
  --color-focus: oklch(58% 0.2 255);
  --font-display: "Space Grotesk", ui-sans-serif, sans-serif;
  --font-body: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --font-outlier: "JetBrains Mono", ui-monospace, monospace;
  --spacing-3xs: 0.25rem;
  --spacing-2xs: 0.5rem;
  --spacing-xs: 0.75rem;
  --spacing-sm: 1rem;
  --spacing-md: 1.5rem;
  --spacing-lg: 2rem;
  --spacing-xl: 3rem;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-md: 1.125rem;
  --text-lg: 1.375rem;
  --text-xl: 1.75rem;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --radius-card: 0.75rem;
  --radius-input: 0.5rem;
}
```

### DTCG `tokens.json`

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "color": {
    "paper": { "$value": "oklch(98.5% 0.006 252)", "$type": "color" },
    "paper-2": { "$value": "oklch(96.5% 0.009 252)", "$type": "color" },
    "ink": { "$value": "oklch(18% 0.038 252)", "$type": "color" },
    "accent": { "$value": "oklch(52% 0.19 255)", "$type": "color" },
    "focus": { "$value": "oklch(58% 0.2 255)", "$type": "color" }
  },
  "font": {
    "display": { "$value": "Space Grotesk, ui-sans-serif, sans-serif", "$type": "fontFamily" },
    "body": { "$value": "IBM Plex Sans, ui-sans-serif, system-ui, sans-serif", "$type": "fontFamily" },
    "outlier": { "$value": "JetBrains Mono, ui-monospace, monospace", "$type": "fontFamily" }
  },
  "space": {
    "xs": { "$value": "0.75rem", "$type": "dimension" },
    "sm": { "$value": "1rem", "$type": "dimension" },
    "md": { "$value": "1.5rem", "$type": "dimension" },
    "lg": { "$value": "2rem", "$type": "dimension" }
  },
  "duration": {
    "micro": { "$value": "120ms", "$type": "duration" },
    "short": { "$value": "220ms", "$type": "duration" },
    "long": { "$value": "420ms", "$type": "duration" }
  }
}
```

### shadcn/ui CSS variables

```css
:root {
  --background: 98.5% 0.006 252;
  --foreground: 18% 0.038 252;
  --card: 99.3% 0.004 252;
  --card-foreground: 18% 0.038 252;
  --popover: 99.3% 0.004 252;
  --popover-foreground: 18% 0.038 252;
  --primary: 52% 0.19 255;
  --primary-foreground: 98.5% 0.006 252;
  --secondary: 93.5% 0.012 252;
  --secondary-foreground: 27% 0.034 252;
  --muted: 88% 0.014 252;
  --muted-foreground: 42% 0.028 252;
  --accent: 52% 0.19 255;
  --accent-foreground: 98.5% 0.006 252;
  --destructive: 52% 0.19 25;
  --destructive-foreground: 98.5% 0.006 252;
  --border: 88% 0.014 252;
  --input: 74% 0.022 252;
  --ring: 58% 0.2 255;
  --radius: 0.75rem;
}
```
