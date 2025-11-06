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
- **File**: `NotoColorEmoji.ttf`
- **Source**: https://github.com/googlefonts/noto-emoji

## Why Bundle Fonts?

The fonts are bundled to ensure consistent rendering across different environments:
- Guarantees calendar images look the same everywhere
- Provides emoji support even when system fonts don't
- Makes the application self-contained and easier to deploy

## Fallback Behavior

If bundled fonts are not found, the application will attempt to use system fonts at these locations:
- `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`
- `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
- `/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf`
