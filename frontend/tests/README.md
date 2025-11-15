# Frontend Tests

This directory contains tests for the ChallengeCtl Web UI.

## Test Structure

- **Unit Tests**: Located alongside source files with `.spec.js` extension
- **Component Tests**: Vue component tests using `@vue/test-utils`
- **Module Tests**: Tests for API, config, router, and websocket modules

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with UI
npm run test:ui

# Generate coverage report
npm run test:coverage

# Run linter
npm run lint

# Auto-fix linting issues
npm run lint:fix
```

## Test Files

- `src/api.spec.js` - Tests for API module
- `src/config.spec.js` - Tests for configuration module
- `src/router.spec.js` - Tests for Vue Router configuration
- `src/views/Dashboard.spec.js` - Tests for Dashboard component
- `src/views/PublicDashboard.spec.js` - Tests for Public Dashboard component
- `src/views/Challenges.spec.js` - Tests for Challenges component

## Technologies

- **Vitest**: Fast test runner built on Vite
- **@vue/test-utils**: Official testing utilities for Vue.js
- **happy-dom**: Lightweight DOM implementation for testing
- **ESLint**: Code quality and style checking

## Coverage

Coverage reports are generated in the `coverage/` directory after running:

```bash
npm run test:coverage
```

View the HTML report:

```bash
open coverage/index.html
```

## CI Integration

Tests are automatically run on:
- Push to main, challengectl-v2, or claude/* branches
- Pull requests that modify frontend code

See `.github/workflows/frontend-ci.yml` for CI configuration.

## Writing Tests

### Component Test Example

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MyComponent from './MyComponent.vue'

describe('MyComponent', () => {
  it('should render correctly', () => {
    const wrapper = mount(MyComponent)
    expect(wrapper.exists()).toBe(true)
  })
})
```

### Module Test Example

```javascript
import { describe, it, expect } from 'vitest'
import myModule from './myModule'

describe('MyModule', () => {
  it('should export expected functions', () => {
    expect(typeof myModule.myFunction).toBe('function')
  })
})
```

## Best Practices

1. **Isolate Tests**: Each test should be independent
2. **Mock External Dependencies**: Use `vi.mock()` for API calls, timers, etc.
3. **Test User Behavior**: Focus on what users see and interact with
4. **Clean Up**: Unmount components and clear mocks in `afterEach()`
5. **Use Descriptive Names**: Test names should clearly describe what they test
6. **Avoid Implementation Details**: Test behavior, not internal implementation

## Troubleshooting

### Tests timing out
- Check for unresolved promises
- Ensure async operations use `await`
- Use `vi.useFakeTimers()` for time-dependent tests

### Mock not working
- Ensure `vi.mock()` is called before imports
- Clear mocks in `beforeEach()` or `afterEach()`
- Check mock paths are correct

### Component not rendering
- Verify all required props are provided
- Check for missing dependencies in mount options
- Use `wrapper.vm.$nextTick()` for async updates
