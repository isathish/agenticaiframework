# Brand assets

Source files are SVG; PNGs are rendered from them with `rsvg-convert`.

| File | Use |
|------|-----|
| `logo.svg` / `logo.png` (512px) | Primary mark: gradient tile, white agent graph. Used as the site logo. |
| `logo-mark-mono.svg` | Single-colour mark (`currentColor`), no tile. For coloured or print backgrounds. |
| `logo-wordmark.svg` / `.png` | Mark + "AgenticAI Framework" for light backgrounds (README, slides). |
| `logo-wordmark-dark.svg` | Wordmark for dark backgrounds. |
| `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` | Browser and home-screen icons. |
| `social-card.svg` / `.png` (1200x630) | Open Graph / Twitter preview image. |

## Concept

Three agents connected by edges form the letter A. The filled apex node is the
orchestrator; the two ring nodes at the base are worker agents; the crossbar is
the shared channel between them.

## Palette

| Token | Hex |
|-------|-----|
| Indigo (primary) | `#6366f1` |
| Indigo dark | `#4f46e5` |
| Cyan (secondary) | `#06b6d4` |
| Text | `#111827` (light) / `#f9fafb` (dark) |

Gradient: 135deg from `#6366f1` to `#06b6d4`.

## Regenerate PNGs

```bash
cd docs/assets
cp logo.svg favicon.svg
rsvg-convert -w 512 -h 512 logo.svg -o logo.png
rsvg-convert -w 32  -h 32  logo.svg -o favicon-32.png
rsvg-convert -w 180 -h 180 logo.svg -o apple-touch-icon.png
rsvg-convert -w 1120 logo-wordmark.svg -o logo-wordmark.png
rsvg-convert -w 1200 -h 630 social-card.svg -o social-card.png
```

Do not add a margin, recolour the mark, or place it on a busy background. Keep
clear space of at least 25% of the tile width around the mark.
