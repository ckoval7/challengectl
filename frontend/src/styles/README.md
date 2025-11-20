# Shared Styles Directory

This directory contains all global CSS files for the ChallengeCtl application. These styles are imported globally in `main.js` and are available throughout the entire app.

## File Structure

```
styles/
├── global.css      # Main entry point (imports all other files)
├── variables.css   # CSS custom properties (colors, spacing, etc.)
├── utilities.css   # Utility classes for common patterns
└── README.md       # This file
```

## Usage

### 1. CSS Variables

Defined in `variables.css`, these can be used anywhere in your components:

```css
.my-component {
  color: var(--app-primary-color);
  padding: var(--spacing-xl);
  border-radius: var(--border-radius-md);
}
```

Available variables:
- **Colors**: `--app-primary-color`, `--app-text-primary`, `--app-text-secondary`
- **Spacing**: `--spacing-xs` through `--spacing-3xl` (4px to 32px)
- **Border Radius**: `--border-radius-sm`, `--border-radius-md`, `--border-radius-lg`
- **Shadows**: `--shadow-sm`, `--shadow-md`, `--shadow-lg`
- **Transitions**: `--transition-fast`, `--transition-base`, `--transition-slow`

### 2. Utility Classes

Defined in `utilities.css`, these can replace inline styles in your Vue templates:

**Before:**
```vue
<div style="margin-bottom: 20px; display: flex; align-items: center;">
```

**After:**
```vue
<div class="mb-xl flex items-center">
```

Available utility classes:
- **Spacing**: `mb-xl`, `mt-sm`, `p-md`, etc.
- **Flexbox**: `flex`, `flex-center`, `flex-between`, `items-center`, etc.
- **Text**: `text-center`, `text-primary`, `font-bold`, `text-xl`, etc.
- **Layout**: `w-full`, `block`, `hidden`, etc.
- **Common components**: `info-box`, `stat-card`, `card-header`, etc.

### 3. Component-Specific Styles

Common reusable component styles are also available as classes:

```vue
<div class="info-box">This is styled consistently</div>

<div class="stat-card">
  <div class="stat-value">42</div>
  <div class="stat-label">Users Online</div>
  <div class="stat-sublabel">Today</div>
</div>
```

## Best Practices

1. **Prefer utility classes over inline styles** when possible
2. **Use CSS variables** for colors and spacing to maintain consistency
3. **Keep component-specific styles** in scoped `<style>` blocks within `.vue` files
4. **Add new variables** to `variables.css` if you need new design tokens
5. **Add new utilities** to `utilities.css` if you find yourself repeating patterns

## Updating Global Styles

To add or modify global styles:

1. **Variables**: Edit `variables.css` for new colors, spacing, or design tokens
2. **Utilities**: Edit `utilities.css` for new utility classes
3. **Base styles**: Edit `global.css` for app-wide element defaults

All changes will be automatically available throughout the app without needing to restart the dev server (hot reload).

## Migration Guide

To convert existing inline styles to use this system:

1. **Replace hard-coded colors** with CSS variables:
   ```css
   /* Old */
   color: #409EFF;

   /* New */
   color: var(--app-primary-color);
   ```

2. **Replace inline spacing** with utility classes:
   ```vue
   <!-- Old -->
   <div style="margin-bottom: 20px">

   <!-- New -->
   <div class="mb-xl">
   ```

3. **Replace common patterns** with pre-built component classes:
   ```vue
   <!-- Old -->
   <div style="padding: 8px 12px; background: var(--el-fill-color-lighter); border-radius: 4px;">

   <!-- New -->
   <div class="info-box">
   ```
