# Assets Directory

This directory contains branding assets for the AgenticAI Framework documentation.

## Required Assets

### 1. Logo (agenticaiframework.png)
- **File**: `agenticaiframework.png`
- **Recommended Size**: 128x128 pixels
- **Format**: PNG with transparency
- **Usage**: Displayed in the navigation bar
- **Design Guidelines**:
  - Simple, recognizable icon
  - Works well at small sizes
  - Good contrast against both light and dark backgrounds
  - Represents AI/Agent concepts

### 2. Favicon (favicon.png)
- **File**: `favicon.png`
- **Recommended Size**: 32x32 or 64x64 pixels
- **Format**: PNG or ICO
- **Usage**: Browser tab icon
- **Design Guidelines**:
  - Very simple, recognizable at tiny sizes
  - High contrast
  - Represents brand identity

## Creating Assets

### Using SVG to PNG Conversion
```bash
# If you have an SVG logo
inkscape agenticaiframework.svg --export-png=agenticaiframework.png --export-width=128 --export-height=128

# For favicon
inkscape agenticaiframework.svg --export-png=favicon.png --export-width=64 --export-height=64
```

### Using ImageMagick
```bash
# Resize existing image to logo size
convert existing-logo.png -resize 128x128 agenticaiframework.png

# Create favicon
convert existing-logo.png -resize 32x32 favicon.png
```

### Using Python (PIL/Pillow)
```python
from PIL import Image

# Create logo
img = Image.open('original.png')
img = img.resize((128, 128), Image.Resampling.LANCZOS)
img.save('agenticaiframework.png', 'PNG')

# Create favicon
img = img.resize((32, 32), Image.Resampling.LANCZOS)
img.save('favicon.png', 'PNG')
```

## Temporary Placeholder

Until custom assets are created, you can use placeholder images or disable the logo/favicon in `mkdocs.yml` by commenting out these lines:

```yaml
# logo: assets/agenticaiframework.png
# favicon: assets/favicon.png
```

## Alternative: Use Emoji/Icon

You can also use Material Design icons or emoji as the logo:

```yaml
theme:
  icon:
    logo: material/robot # Material Design icon
  # Or use emoji
  # logo: 
```

## Brand Colors

Recommended colors for AgenticAI Framework branding:

- **Primary**: Indigo (#3F51B5)
- **Accent**: Amber (#FFC107)
- **Background (Light)**: White (#FFFFFF)
- **Background (Dark)**: Slate (#1E1E1E)
- **Text**: Dark Gray (#212121) / White (#FFFFFF)

## File Structure

```
docs/assets/
├── README.md # This file
├── agenticaiframework.png # Main logo (128x128)
├── favicon.png # Favicon (32x32 or 64x64)
├── agenticaiframework.svg # Optional: Vector version
├── banner.png # Optional: Social media banner
└── screenshots/ # Optional: Screenshots folder
```

## Social Media Assets (Optional)

### Open Graph Image
- **Size**: 1200x630 pixels
- **File**: `og-image.png`
- **Usage**: Social media previews

### Twitter Card Image
- **Size**: 1200x600 pixels
- **File**: `twitter-card.png`
- **Usage**: Twitter link previews

## Testing Assets

After adding assets, test them:

1. **Local Development**:
   ```bash
   mkdocs serve
   ```

2. **Check**:
   - Logo appears in navigation bar
   - Favicon appears in browser tab
   - Images render correctly in light/dark mode
   - Proper sizing and alignment

## Quick Start: Placeholder Creation

If you need quick placeholders for testing:

```python
from PIL import Image, ImageDraw, ImageFont

# Create logo placeholder
img = Image.new('RGBA', (128, 128), (63, 81, 181, 255))
draw = ImageDraw.Draw(img)
draw.text((40, 50), "AI", fill=(255, 255, 255, 255), font=ImageFont.truetype("Arial", 48))
img.save('agenticaiframework.png')

# Create favicon placeholder
img_small = img.resize((32, 32), Image.Resampling.LANCZOS)
img_small.save('favicon.png')
```

---

**Status**: Directory created, assets pending 
**Action Required**: Add agenticaiframework.png and favicon.png files or comment out logo/favicon in mkdocs.yml
