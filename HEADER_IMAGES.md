# Responsive Header Images Guide

This guide specifies the image sizes you should create for responsive header images on dctech.events.

## Quick Answer

For dctech.events, create these image sizes:

### Social Media Sharing (Priority 1)
- **1200×630 px** - Primary Open Graph and Twitter Card image
  - Format: PNG or JPG
  - Max file size: 5MB
  - Aspect ratio: 1.91:1

### Responsive Web Display (Priority 2)
- **640×336 px** - Mobile devices (up to 768px width)
- **1024×538 px** - Tablet devices 
- **1920×1008 px** - Desktop/laptop screens
- **2400×1260 px** - Retina/4K displays (optional but recommended)

All responsive images should maintain the same 1.91:1 aspect ratio for consistency.

### Icons (Priority 3)
- **180×180 px** - Apple Touch Icon
- **192×192 px** - Android Chrome icon
- **512×512 px** - Android Chrome icon (large)
- **32×32 px** - Standard favicon
- **16×16 px** - Browser favicon

---

## Detailed Specifications

### 1. Social Media Open Graph Images

#### Open Graph (Facebook, LinkedIn, Slack)
**Recommended Size:** 1200×630 px  
**Minimum Size:** 600×315 px  
**Aspect Ratio:** 1.91:1  
**Format:** JPG, PNG, or WebP  
**Max File Size:** 8MB (keep under 1MB for performance)

The 1200×630 size ensures your image looks sharp on high-resolution displays and won't be cropped on any social platform.

#### Twitter Cards
**Large Image Card:** 1200×628 px  
**Aspect Ratio:** 1.91:1  
**Format:** JPG, PNG, GIF, or WebP  
**Max File Size:** 5MB (keep under 1MB for performance)

**Summary Card:** 120×120 px minimum (1:1 ratio)  
Only needed if using summary card instead of summary_large_image.

### 2. Responsive Web Images

Based on the site's CSS breakpoint at 768px, create these sizes:

#### Mobile (320px - 767px screens)
**Image Size:** 640×336 px  
**Use Case:** Smartphones in portrait and landscape  
**DPR Coverage:** 1x for 640px screens, 2x for 320px screens

#### Tablet (768px - 1024px screens)
**Image Size:** 1024×538 px  
**Use Case:** Tablets and small laptops  
**DPR Coverage:** 1x for 1024px screens, 2x for 512px screens

#### Desktop (1025px - 1920px screens)
**Image Size:** 1920×1008 px  
**Use Case:** Standard desktop and laptop screens  
**DPR Coverage:** 1x for 1920px (Full HD) screens

#### Retina/4K (High DPI displays)
**Image Size:** 2400×1260 px  
**Use Case:** 4K monitors, Retina displays  
**DPR Coverage:** 2x for 1200px screens, covers high-DPI devices

### 3. Icons and Favicons

#### Apple Touch Icon
**Size:** 180×180 px  
**Format:** PNG  
**Purpose:** iOS home screen icon

#### Android Chrome Icons
**Sizes:** 192×192 px and 512×512 px  
**Format:** PNG  
**Purpose:** Android home screen and splash screens

#### Browser Favicons
**Sizes:** 32×32 px and 16×16 px  
**Format:** ICO or PNG  
**Purpose:** Browser tabs and bookmarks

---

## Implementation Example

### File Structure
```
static/
  images/
    og-image.png              # 1200×630 - Primary social sharing
    header-mobile.png         # 640×336 - Mobile responsive
    header-tablet.png         # 1024×538 - Tablet responsive
    header-desktop.png        # 1920×1008 - Desktop responsive
    header-retina.png         # 2400×1260 - High-DPI displays
    icon-180.png              # 180×180 - Apple touch icon
    icon-192.png              # 192×192 - Android Chrome
    icon-512.png              # 512×512 - Android Chrome large
    favicon-32.png            # 32×32 - Standard favicon
    favicon-16.png            # 16×16 - Browser favicon
```

### Meta Tags (Add to base.html)

```html
<!-- Open Graph / Facebook -->
<meta property="og:image" content="{{ base_url }}/static/images/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:type" content="image/png">

<!-- Twitter -->
<meta name="twitter:image" content="{{ base_url }}/static/images/og-image.png">
<meta name="twitter:card" content="summary_large_image">

<!-- Apple Touch Icon -->
<link rel="apple-touch-icon" sizes="180x180" href="/static/images/icon-180.png">

<!-- Favicons -->
<link rel="icon" type="image/png" sizes="32x32" href="/static/images/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/static/images/favicon-16.png">

<!-- Android Chrome -->
<link rel="manifest" href="/manifest.json">
```

### Responsive Picture Element (for hero images)

```html
<picture>
  <source media="(min-width: 1920px)" srcset="/static/images/header-retina.png 1x, /static/images/header-retina.png 2x">
  <source media="(min-width: 1024px)" srcset="/static/images/header-desktop.png 1x, /static/images/header-retina.png 2x">
  <source media="(min-width: 768px)" srcset="/static/images/header-tablet.png 1x, /static/images/header-desktop.png 2x">
  <source media="(max-width: 767px)" srcset="/static/images/header-mobile.png 1x, /static/images/header-tablet.png 2x">
  <img src="/static/images/header-desktop.png" alt="DC Tech Events" loading="lazy">
</picture>
```

### CSS Background Image (alternative approach)

```css
header {
  background-image: url('/static/images/header-mobile.png');
  background-size: cover;
  background-position: center;
}

@media (min-width: 768px) {
  header {
    background-image: url('/static/images/header-tablet.png');
  }
}

@media (min-width: 1024px) {
  header {
    background-image: url('/static/images/header-desktop.png');
  }
}

@media (min-width: 1920px) {
  header {
    background-image: url('/static/images/header-retina.png');
  }
}

@media (-webkit-min-device-pixel-ratio: 2), (min-resolution: 192dpi) {
  header {
    background-image: url('/static/images/header-retina.png');
  }
}
```

---

## Image Creation Guidelines

### Design Considerations
1. **Safe Zone:** Keep important text/logos in the center 1000×524 px area to avoid cropping on different platforms
2. **Text Readability:** Ensure text is readable at the smallest size (640×336 px)
3. **Contrast:** Use sufficient contrast for accessibility
4. **File Format:** 
   - PNG for images with text or transparency
   - JPG for photographic images (better compression)
   - WebP for best compression (with fallback)

### Content Guidelines
- Include site name "DC Tech Events" prominently
- Consider adding the tagline: "Technology conferences and meetups in and around Washington, DC"
- Use DC landmarks or tech-related imagery
- Maintain brand consistency with site colors:
  - Primary: #2563eb (blue)
  - Text: #1f2937 (dark gray)
  - Background: #ffffff (white)
  - Accent: #fef3c7 (yellow/gold)

### Optimization
1. **Compress images** to reduce file size
   - Use tools like TinyPNG, ImageOptim, or Squoosh
   - Aim for under 200KB per image
   - Social sharing images can be up to 1MB
2. **Use modern formats** when possible
   - WebP with JPG/PNG fallback
   - AVIF for cutting-edge browsers (with fallback)
3. **Lazy loading** for non-critical images
4. **CDN delivery** for faster loading worldwide

### Testing Checklist
- [ ] Test Open Graph image on [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/)
- [ ] Test Twitter Card on [Twitter Card Validator](https://cards-dev.twitter.com/validator)
- [ ] Test responsive images on multiple devices/screen sizes
- [ ] Verify image loads quickly (under 2 seconds)
- [ ] Check accessibility with screen readers
- [ ] Validate HTML and meta tags

---

## manifest.json Example

Create `static/manifest.json` for Android/Chrome icons:

```json
{
  "name": "DC Tech Events",
  "short_name": "DC Tech",
  "description": "Technology conferences and meetups in and around Washington, DC",
  "icons": [
    {
      "src": "/static/images/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/images/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ],
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2563eb"
}
```

---

## Tools and Resources

### Design Tools
- [Figma](https://www.figma.com/) - Web-based design tool
- [Canva](https://www.canva.com/) - Easy template-based designs
- [Photoshop](https://www.adobe.com/products/photoshop.html) - Professional image editing
- [GIMP](https://www.gimp.org/) - Free Photoshop alternative

### Image Optimization Tools
- [Squoosh](https://squoosh.app/) - Browser-based compression
- [TinyPNG](https://tinypng.com/) - PNG/JPG compression
- [ImageOptim](https://imageoptim.com/) - Mac image optimizer
- [Sharp](https://sharp.pixelplumbing.com/) - Node.js image processing

### Testing Tools
- [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/)
- [Twitter Card Validator](https://cards-dev.twitter.com/validator)
- [LinkedIn Post Inspector](https://www.linkedin.com/post-inspector/)
- [Open Graph Checker](https://opengraphcheck.com/)

### Reference Documentation
- [Open Graph Protocol](https://ogp.me/)
- [Twitter Card Documentation](https://developer.twitter.com/en/docs/twitter-for-websites/cards/overview/abouts-cards)
- [Web.dev Image Guide](https://web.dev/fast/#optimize-your-images)
- [MDN Responsive Images](https://developer.mozilla.org/en-US/docs/Learn/HTML/Multimedia_and_embedding/Responsive_images)

---

## Summary

**Minimum Required (Start Here):**
1. **1200×630 px** - Social media sharing image (og-image.png)
2. **180×180 px** - Apple touch icon
3. **32×32 px and 16×16 px** - Favicons

**Full Responsive Set (Recommended):**
- Add 640×336, 1024×538, 1920×1008, and 2400×1260 px for responsive web display
- Add 192×192 and 512×512 px for Android icons
- Create manifest.json for PWA support

**Remember:** All header images should maintain the 1.91:1 aspect ratio for consistency across platforms.
