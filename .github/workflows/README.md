# CI/CD Configuration Guide

This document provides instructions for configuring the CI/CD workflows in this repository.

## Overview

The repository includes 9 comprehensive GitHub Actions workflows:

1. **backend-ci.yml** - Backend testing with coverage
2. **frontend-ci.yml** - Frontend testing with coverage
3. **code-quality.yml** - Code quality and security scanning
4. **coverage-report.yml** - Combined coverage reporting
5. **dependency-check.yml** - Dependency vulnerability monitoring
6. **pr-validation.yml** - Pull request validation
7. **docker-build.yml** - Docker build testing
8. **challengectl-test.yaml** - System tests
9. **wav-format-check.yaml** - Asset validation

## Required Secrets

Some workflows require GitHub repository secrets to be configured for full functionality.

### Safety API Key (Optional but Recommended)

The `code-quality.yml` workflow uses [Safety](https://pyup.io/safety/) to scan Python dependencies for known security vulnerabilities.

**To enable Safety scanning:**

1. Get a free API key from [Safety](https://pyup.io/safety/)
2. In your GitHub repository, go to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `SAFETY_API_KEY`
5. Value: Your Safety API key
6. Click "Add secret"

**If not configured:**
- The workflow will skip Safety scanning with a warning message
- Other security checks (Bandit) will still run
- The workflow will not fail

## Workflow Triggers

### Automatic Triggers

- **Push to master/challengectl-v2/claude/** branches:
  - backend-ci.yml
  - frontend-ci.yml
  - code-quality.yml
  - docker-build.yml

- **Pull Requests:**
  - All CI workflows
  - pr-validation.yml
  - coverage-report.yml (with PR comments)

- **Schedule (Weekly Monday 9 AM UTC):**
  - dependency-check.yml

### Manual Triggers

You can manually trigger `dependency-check.yml`:
1. Go to Actions tab
2. Select "Dependency Check" workflow
3. Click "Run workflow"

## Artifacts

Workflows generate and upload various artifacts:

| Workflow | Artifact | Retention |
|----------|----------|-----------|
| backend-ci.yml | server-coverage | 30 days |
| frontend-ci.yml | frontend-coverage, frontend-build | 7-30 days |
| code-quality.yml | bandit-security-report, safety-vulnerability-report | 30 days |
| coverage-report.yml | coverage-summary | 90 days |
| dependency-check.yml | python-dependency-audit, npm-dependency-audit | 90 days |

## Coverage Thresholds

- **Frontend:** Warning if < 50%
- **Backend:** Warning if < 40%

Thresholds are informational only and do not fail builds.

## Running Tests Locally

### Backend Tests

```bash
# Install dependencies
pip install -r requirements-server.txt
pip install pytest pytest-cov

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=server --cov-report=html --cov-report=term-missing

# Run only integration tests
pytest tests/ -m integration
```

### Frontend Tests

```bash
cd frontend

# Install dependencies
npm ci

# Run tests
npm test

# Run with coverage
npm run test:coverage
```

## Security Scanning Tools

The CI/CD pipeline includes multiple security tools:

- **Bandit** - Python security issues scanner
- **Safety** - Python dependency vulnerability scanner (requires API key)
- **pip-audit** - Python package vulnerability auditing
- **npm audit** - NPM dependency vulnerability scanner
- **Secret scanning** - Detects hardcoded secrets in PRs

## Troubleshooting

### "No file matched to requirements.txt"

This is expected - the repository uses `requirements-server.txt` and `requirements-runner.txt`. The workflows are configured correctly.

### Safety scan skipped

Configure the `SAFETY_API_KEY` secret as described above.

### Coverage reports not appearing

Coverage artifacts are uploaded but not automatically displayed. Download them from the workflow run's artifacts section.

## Contributing

When adding new workflows:

1. Test locally when possible
2. Use `continue-on-error: true` for non-critical steps
3. Upload artifacts for debugging
4. Document any required secrets in this file
5. Set appropriate retention periods for artifacts
