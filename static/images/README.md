# Header Images Directory

This directory should contain the responsive header images for the site.

📄 **Quick Reference:** See `SIZES_QUICK_REFERENCE.txt` in this directory for a visual overview of all required sizes.

📚 **Complete Guide:** See [HEADER_IMAGES.md](../../HEADER_IMAGES.md) in the root directory for:
- Complete specifications for all required image sizes
- Implementation examples
- Design guidelines
- Optimization recommendations

## Required Files

### Social Media Sharing (Priority 1)
- `og-image.png` - 1200×630 px

### Responsive Web Display (Priority 2)
- `header-mobile.png` - 640×336 px
- `header-tablet.png` - 1024×538 px
- `header-desktop.png` - 1920×1008 px
- `header-retina.png` - 2400×1260 px

### Icons (Priority 3)
- `icon-180.png` - 180×180 px (Apple Touch Icon)
- `icon-192.png` - 192×192 px (Android Chrome)
- `icon-512.png` - 512×512 px (Android Chrome Large)
- `favicon-32.png` - 32×32 px
- `favicon-16.png` - 16×16 px

## Next Steps

1. Create images following the specifications in HEADER_IMAGES.md
2. Place them in this directory
3. Uncomment the meta tags in `templates/base.html`
4. Rename `manifest.json.template` to `manifest.json` in the parent directory
5. Test with social media debuggers and on various devices
