# Frontend Dependencies Guide

## Overview

This project separates dependencies into two categories to optimize for both development workflow and production deployment:

- **dependencies**: Runtime packages required for the application to function
- **devDependencies**: Development tools (linting, testing) used during development and CI/CD

## Development Installation

Install all dependencies including development tools:

```bash
npm install
# or
npm ci
```

This installs:
- Runtime dependencies (Vue, Element Plus, axios, etc.)
- Development tools (ESLint, Vitest, testing libraries)
- Total: ~356 packages

Available commands:
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Auto-fix linting issues
- `npm run test` - Run tests
- `npm run test:coverage` - Run tests with coverage

## Production Installation

Install only runtime dependencies (excludes dev tools):

```bash
npm ci --omit=dev
# or
npm install --production
```

This installs:
- Runtime dependencies only
- Total: ~116 packages (67% reduction)

Available commands:
- `npm run build` - Build for production
- `npm run preview` - Preview production build

## Bundle Optimization

The build is optimized with:

1. **Lazy Loading**: All route components use dynamic imports
2. **Manual Chunks**: Vendor libraries separated for better caching:
   - `element-plus`: Element Plus UI library (~894 KB)
   - `vue-vendor`: Vue core and router (~101 KB)
   - `vendor-utils`: Axios, Socket.io, QRCode (~102 KB)
   - Individual route chunks: 1-27 KB each

### Build Output Example

```
dist/assets/element-plus-*.js      894 KB │ gzip: 288 KB
dist/assets/vue-vendor-*.js        101 KB │ gzip:  39 KB
dist/assets/vendor-utils-*.js      102 KB │ gzip:  36 KB
dist/assets/Dashboard-*.js           8 KB │ gzip:   3 KB
dist/assets/Login-*.js               5 KB │ gzip:   2 KB
...
```

## CI/CD Integration

GitHub Actions workflows use full installation (`npm ci`) to enable:
- Linting validation
- Test execution
- Coverage reporting

Production builds can use `npm ci --omit=dev` to reduce deployment size.

## Docker/Container Builds

If building Docker images, use this pattern:

```dockerfile
# Development stage
FROM node:20 AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Production stage
FROM node:20 AS prod
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
RUN npm run build
```
