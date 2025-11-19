# ChallengeCtl Test Suite

This directory contains the automated test suite for the ChallengeCtl server components.

## Test Structure

- `test_database.py` - Unit tests for database operations
- `test_crypto.py` - Unit tests for cryptographic utilities
- `test_integration.py` - Integration tests for end-to-end workflows

## Running Tests

### Run all tests:
```bash
pytest tests/
```

### Run with coverage:
```bash
pytest tests/ --cov=server --cov-report=html --cov-report=term-missing
```

### Run specific test file:
```bash
pytest tests/test_database.py -v
```

### Run tests by marker:
```bash
pytest tests/ -m integration  # Run only integration tests
pytest tests/ -m unit         # Run only unit tests
```

## Test Markers

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests testing multiple components together
- `@pytest.mark.slow` - Tests that take longer to run

## Dependencies

Tests require the following packages:
- pytest
- pytest-cov
- All packages from requirements-server.txt

Install with:
```bash
pip install -r requirements-server.txt
pip install pytest pytest-cov
```

## CI/CD Integration

Tests are automatically run in the CI/CD pipeline:
- Backend CI runs unit tests on Python 3.9, 3.12, and 3.13
- Integration tests run separately
- Coverage reports are generated and uploaded as artifacts
- Coverage thresholds are checked (minimum 40% for backend)
