# Bundled Fonts

This directory contains open-source fonts used for generating week calendar images.

## Fonts Included

### DejaVu Sans (Bold and Regular)
- **License**: DejaVu Fonts License (based on Bitstream Vera Fonts)
- **Usage**: Main text rendering
- **Files**: `DejaVuSans-Bold.ttf`, `DejaVuSans.ttf`
- **Source**: https://dejavu-fonts.github.io/

### Noto Color Emoji
- **License**: SIL Open Font License 1.1
- **Usage**: Emoji rendering in event titles
- **File**: `NotoColorEmoji.ttf` (11MB)
- **Source**: https://github.com/googlefonts/noto-emoji
- **Requirements**: Pillow 10.0.0+ for color emoji support

## Why Bundle Fonts?

The fonts are bundled to ensure consistent rendering across different environments:
- Guarantees calendar images look the same everywhere
- Provides emoji support even when system fonts don't
- Makes the application self-contained and easier to deploy

## Emoji Support

Emoji rendering requires:
- **Pillow 10.0.0 or higher** (for `embedded_color=True` support)
- The bundled `NotoColorEmoji.ttf` font
- If requirements aren't met, emoji will be skipped but text will still render

When an event title contains emoji (e.g., "🚀 Tech Launch"), the system:
1. Detects the emoji in the text
2. Renders using NotoColorEmoji font with `embedded_color=True`
3. Falls back to regular font (emoji won't show) if color rendering fails

## Fallback Behavior

If bundled fonts are not found, the application will attempt to use system fonts at these locations:
- `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`
- `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
- `/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf`
