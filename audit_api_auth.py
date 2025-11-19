#!/usr/bin/env python3
"""
API Authentication Audit Script for ChallengeCtl

This script audits all API endpoints by testing them with different authentication methods:
- Valid admin credentials (username/password/TOTP)
- Valid runner API key
- Valid provisioning API key
- Valid enrollment token
- Invalid/nonsense credentials
- No credentials

Reports green (✓) for expected responses and red (✗) for unexpected responses.

Usage:
    ./audit_api_auth.py --url http://localhost:5000 \\
        --admin-username admin \\
        --admin-password yourpassword \\
        --admin-totp-secret YOURSECRET \\
        --runner-api-key runner_key_here \\
        --provisioning-api-key prov_key_here \\
        --enrollment-token enroll_token_here

    Or use environment variables:
        AUDIT_URL=http://localhost:5000
        AUDIT_ADMIN_USERNAME=admin
        AUDIT_ADMIN_PASSWORD=yourpassword
        AUDIT_ADMIN_TOTP_SECRET=YOURSECRET
        AUDIT_RUNNER_API_KEY=runner_key_here
        AUDIT_PROVISIONING_API_KEY=prov_key_here
        AUDIT_ENROLLMENT_TOKEN=enroll_token_here
"""

import argparse
import os
import sys
import requests
import json
import pyotp
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class AuthType(Enum):
    """Types of authentication to test."""
    NONE = "none"
    ADMIN = "admin"
    RUNNER = "runner"
    PROVISIONING = "provisioning"
    ENROLLMENT = "enrollment"
    INVALID = "invalid"


class ExpectedResult(Enum):
    """Expected HTTP status code categories."""
    SUCCESS = "2xx"  # 200-299
    UNAUTHORIZED = "401"
    FORBIDDEN = "403"
    NOT_FOUND = "404"
    BAD_REQUEST = "400"


@dataclass
class EndpointTest:
    """Defines an API endpoint and its expected authentication behavior."""
    method: str
    path: str
    description: str
    expected_auth: List[AuthType]  # Auth types that should succeed
    body: Optional[Dict] = None  # Optional request body
    path_params: Optional[Dict] = None  # Optional path parameters


class APIAuthAuditor:
    """Audits API authentication for all endpoints."""

    # ANSI color codes
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def __init__(self, base_url: str, admin_username: Optional[str] = None,
                 admin_password: Optional[str] = None, admin_totp_secret: Optional[str] = None,
                 runner_api_key: Optional[str] = None, provisioning_api_key: Optional[str] = None,
                 enrollment_token: Optional[str] = None):
        """Initialize the auditor with credentials."""
        self.base_url = base_url.rstrip('/')
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.admin_totp_secret = admin_totp_secret
        self.runner_api_key = runner_api_key
        self.provisioning_api_key = provisioning_api_key
        self.enrollment_token = enrollment_token

        self.admin_session = None
        self.admin_csrf_token = None
        self.session = requests.Session()

        # Test results tracking
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0

    def authenticate_admin(self) -> bool:
        """Authenticate as admin and get session cookies."""
        if not all([self.admin_username, self.admin_password, self.admin_totp_secret]):
            return False

        try:
            # Step 1: Login with username/password
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json={
                    'username': self.admin_username,
                    'password': self.admin_password
                }
            )

            if response.status_code != 200:
                print(f"{self.YELLOW}⚠ Admin login failed (step 1): {response.status_code}{self.RESET}")
                return False

            # Step 2: Verify TOTP
            totp = pyotp.TOTP(self.admin_totp_secret)
            totp_code = totp.now()

            response = self.session.post(
                f"{self.base_url}/api/auth/verify-totp",
                json={'totp_code': totp_code}
            )

            if response.status_code != 200:
                print(f"{self.YELLOW}⚠ Admin TOTP verification failed: {response.status_code}{self.RESET}")
                return False

            # Get CSRF token from cookie
            self.admin_csrf_token = self.session.cookies.get('csrf_token')
            if not self.admin_csrf_token:
                print(f"{self.YELLOW}⚠ No CSRF token received{self.RESET}")
                return False

            print(f"{self.GREEN}✓ Admin authentication successful{self.RESET}")
            return True

        except Exception as e:
            print(f"{self.YELLOW}⚠ Admin authentication error: {e}{self.RESET}")
            return False

    def make_request(self, method: str, path: str, auth_type: AuthType,
                    body: Optional[Dict] = None) -> requests.Response:
        """Make a request with specified authentication type."""
        url = f"{self.base_url}{path}"
        headers = {}

        # Set authentication based on type
        if auth_type == AuthType.ADMIN:
            if self.admin_csrf_token:
                headers['X-CSRF-Token'] = self.admin_csrf_token
            # Session cookies are automatically included
            response = self.session.request(method, url, json=body, headers=headers)

        elif auth_type == AuthType.RUNNER:
            if self.runner_api_key:
                headers['Authorization'] = f'Bearer {self.runner_api_key}'
            new_session = requests.Session()
            response = new_session.request(method, url, json=body, headers=headers)

        elif auth_type == AuthType.PROVISIONING:
            if self.provisioning_api_key:
                headers['Authorization'] = f'Bearer {self.provisioning_api_key}'
            new_session = requests.Session()
            response = new_session.request(method, url, json=body, headers=headers)

        elif auth_type == AuthType.ENROLLMENT:
            # Enrollment token is typically sent in the request body
            if self.enrollment_token and body:
                body = body.copy()
                body['enrollment_token'] = self.enrollment_token
            new_session = requests.Session()
            response = new_session.request(method, url, json=body, headers=headers)

        elif auth_type == AuthType.INVALID:
            headers['Authorization'] = 'Bearer invalid_nonsense_token_12345'
            new_session = requests.Session()
            response = new_session.request(method, url, json=body, headers=headers)

        else:  # AuthType.NONE
            new_session = requests.Session()
            response = new_session.request(method, url, json=body, headers=headers)

        return response

    def check_result(self, endpoint: EndpointTest, auth_type: AuthType,
                    response: requests.Response) -> Tuple[bool, str]:
        """Check if the response matches expected behavior."""
        status = response.status_code

        # Determine if this auth type should succeed for this endpoint
        should_succeed = auth_type in endpoint.expected_auth

        if should_succeed:
            # Should get 2xx response
            if 200 <= status < 300:
                return True, f"Expected success, got {status}"
            else:
                return False, f"Expected 2xx, got {status}"
        else:
            # Should get 401 (Unauthorized) or 403 (Forbidden)
            # Some endpoints may return 400 for malformed requests
            if status in [401, 403]:
                return True, f"Expected auth failure, got {status}"
            elif status == 400 and auth_type == AuthType.INVALID:
                # 400 is acceptable for invalid data
                return True, f"Expected auth failure, got {status}"
            elif status == 404:
                # 404 might be acceptable if path doesn't exist
                return True, f"Expected auth failure, got {status}"
            elif 200 <= status < 300:
                return False, f"Expected auth failure (401/403), got {status} SUCCESS - SECURITY ISSUE!"
            else:
                # Other errors might be acceptable
                return True, f"Expected auth failure, got {status}"

    def test_endpoint(self, endpoint: EndpointTest) -> Dict[str, any]:
        """Test an endpoint with all authentication types."""
        results = {}

        # Get actual path with parameters if needed
        path = endpoint.path
        if endpoint.path_params:
            for param, value in endpoint.path_params.items():
                path = path.replace(f'<{param}>', str(value))

        # Test with each auth type
        auth_types_to_test = [
            AuthType.ADMIN,
            AuthType.RUNNER,
            AuthType.PROVISIONING,
            AuthType.ENROLLMENT,
            AuthType.INVALID,
            AuthType.NONE,
        ]

        for auth_type in auth_types_to_test:
            # Skip if we don't have the credentials for this auth type
            if auth_type == AuthType.ADMIN and not self.admin_csrf_token:
                results[auth_type] = {'skipped': True, 'reason': 'No admin credentials'}
                continue
            if auth_type == AuthType.RUNNER and not self.runner_api_key:
                results[auth_type] = {'skipped': True, 'reason': 'No runner API key'}
                continue
            if auth_type == AuthType.PROVISIONING and not self.provisioning_api_key:
                results[auth_type] = {'skipped': True, 'reason': 'No provisioning API key'}
                continue
            if auth_type == AuthType.ENROLLMENT and not self.enrollment_token:
                results[auth_type] = {'skipped': True, 'reason': 'No enrollment token'}
                continue

            try:
                response = self.make_request(endpoint.method, path, auth_type, endpoint.body)
                passed, message = self.check_result(endpoint, auth_type, response)

                results[auth_type] = {
                    'passed': passed,
                    'status': response.status_code,
                    'message': message
                }

                self.total_tests += 1
                if passed:
                    self.passed_tests += 1
                else:
                    self.failed_tests += 1

            except Exception as e:
                results[auth_type] = {
                    'passed': False,
                    'status': None,
                    'message': f'Exception: {str(e)}'
                }
                self.total_tests += 1
                self.failed_tests += 1

        return results

    def print_test_result(self, endpoint: EndpointTest, results: Dict[str, any]):
        """Print the results for an endpoint test."""
        print(f"\n{self.BOLD}{endpoint.method} {endpoint.path}{self.RESET}")
        print(f"  {endpoint.description}")

        for auth_type in [AuthType.ADMIN, AuthType.RUNNER, AuthType.PROVISIONING,
                         AuthType.ENROLLMENT, AuthType.INVALID, AuthType.NONE]:
            result = results.get(auth_type, {})

            if result.get('skipped'):
                symbol = f"{self.YELLOW}⊘{self.RESET}"
                self.skipped_tests += 1
                print(f"    {symbol} {auth_type.value:15s} - SKIPPED: {result['reason']}")
            elif result.get('passed'):
                symbol = f"{self.GREEN}✓{self.RESET}"
                print(f"    {symbol} {auth_type.value:15s} - {result['message']}")
            else:
                symbol = f"{self.RED}✗{self.RESET}"
                print(f"    {symbol} {auth_type.value:15s} - {result['message']}")

    def run_audit(self):
        """Run the complete authentication audit."""
        print(f"{self.BOLD}{self.BLUE}")
        print("=" * 80)
        print("ChallengeCtl API Authentication Audit")
        print("=" * 80)
        print(f"{self.RESET}\n")

        print(f"Base URL: {self.base_url}")
        print(f"Admin credentials: {'✓' if self.admin_username else '✗'}")
        print(f"Runner API key: {'✓' if self.runner_api_key else '✗'}")
        print(f"Provisioning API key: {'✓' if self.provisioning_api_key else '✗'}")
        print(f"Enrollment token: {'✓' if self.enrollment_token else '✗'}")
        print()

        # Authenticate as admin if credentials provided
        if self.admin_username:
            if not self.authenticate_admin():
                print(f"{self.YELLOW}⚠ Continuing without admin authentication{self.RESET}\n")

        # Define all endpoints to test
        endpoints = self._get_endpoints_to_test()

        # Run tests
        for endpoint in endpoints:
            results = self.test_endpoint(endpoint)
            self.print_test_result(endpoint, results)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print audit summary."""
        print(f"\n{self.BOLD}{self.BLUE}")
        print("=" * 80)
        print("Audit Summary")
        print("=" * 80)
        print(f"{self.RESET}")

        total = self.total_tests
        passed = self.passed_tests
        failed = self.failed_tests
        skipped = self.skipped_tests

        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"Total tests:   {total}")
        print(f"{self.GREEN}Passed tests:  {passed}{self.RESET}")
        print(f"{self.RED}Failed tests:  {failed}{self.RESET}")
        print(f"{self.YELLOW}Skipped tests: {skipped}{self.RESET}")
        print(f"Pass rate:     {pass_rate:.1f}%")

        if failed > 0:
            print(f"\n{self.RED}{self.BOLD}⚠ SECURITY ISSUES DETECTED!{self.RESET}")
            print(f"{self.RED}Review the failed tests above for potential security vulnerabilities.{self.RESET}")
            return 1
        else:
            print(f"\n{self.GREEN}{self.BOLD}✓ All tests passed!{self.RESET}")
            return 0

    def _get_endpoints_to_test(self) -> List[EndpointTest]:
        """Return list of all endpoints to test."""
        return [
            # Public endpoints
            EndpointTest(
                method='GET',
                path='/api/health',
                description='Health check endpoint',
                expected_auth=[AuthType.NONE, AuthType.ADMIN, AuthType.RUNNER,
                             AuthType.PROVISIONING, AuthType.ENROLLMENT, AuthType.INVALID]
            ),
            EndpointTest(
                method='GET',
                path='/api/public/challenges',
                description='Public challenges list',
                expected_auth=[AuthType.NONE, AuthType.ADMIN, AuthType.RUNNER,
                             AuthType.PROVISIONING, AuthType.ENROLLMENT, AuthType.INVALID]
            ),

            # Admin authentication endpoints
            EndpointTest(
                method='GET',
                path='/api/auth/session',
                description='Get current session info',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='POST',
                path='/api/auth/logout',
                description='Logout current session',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='POST',
                path='/api/auth/change-password',
                description='Change user password',
                expected_auth=[AuthType.ADMIN],
                body={'current_password': 'dummy', 'new_password': 'dummy'}
            ),

            # User management (admin only)
            EndpointTest(
                method='GET',
                path='/api/users',
                description='List all users',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='POST',
                path='/api/users',
                description='Create new user',
                expected_auth=[AuthType.ADMIN],
                body={'username': 'testuser', 'password': 'testpass'}
            ),
            EndpointTest(
                method='PUT',
                path='/api/users/<username>',
                description='Update user',
                expected_auth=[AuthType.ADMIN],
                path_params={'username': 'testuser'},
                body={'password': 'newpass'}
            ),
            EndpointTest(
                method='DELETE',
                path='/api/users/<username>',
                description='Delete user',
                expected_auth=[AuthType.ADMIN],
                path_params={'username': 'testuser'}
            ),

            # Runner endpoints (runner API key only)
            EndpointTest(
                method='POST',
                path='/api/runners/register',
                description='Register runner (deprecated)',
                expected_auth=[AuthType.RUNNER],
                body={'hostname': 'test-runner', 'devices': []}
            ),
            EndpointTest(
                method='POST',
                path='/api/runners/<runner_id>/heartbeat',
                description='Runner heartbeat',
                expected_auth=[AuthType.RUNNER],
                path_params={'runner_id': 'test-runner-id'},
                body={'hostname': 'test-runner', 'status': 'idle'}
            ),
            EndpointTest(
                method='POST',
                path='/api/runners/<runner_id>/signout',
                description='Runner signout',
                expected_auth=[AuthType.RUNNER],
                path_params={'runner_id': 'test-runner-id'}
            ),
            EndpointTest(
                method='GET',
                path='/api/runners/<runner_id>/task',
                description='Get runner task',
                expected_auth=[AuthType.RUNNER],
                path_params={'runner_id': 'test-runner-id'}
            ),
            EndpointTest(
                method='POST',
                path='/api/runners/<runner_id>/complete',
                description='Complete runner task',
                expected_auth=[AuthType.RUNNER],
                path_params={'runner_id': 'test-runner-id'},
                body={'task_id': 'test-task', 'status': 'completed'}
            ),
            EndpointTest(
                method='POST',
                path='/api/runners/<runner_id>/log',
                description='Send runner log',
                expected_auth=[AuthType.RUNNER],
                path_params={'runner_id': 'test-runner-id'},
                body={'level': 'INFO', 'message': 'test'}
            ),

            # Dashboard (admin only)
            EndpointTest(
                method='GET',
                path='/api/dashboard',
                description='Get dashboard data',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='GET',
                path='/api/logs',
                description='Get system logs',
                expected_auth=[AuthType.ADMIN]
            ),

            # Runner management (admin only)
            EndpointTest(
                method='GET',
                path='/api/runners',
                description='List all runners',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='GET',
                path='/api/runners/<runner_id>',
                description='Get runner details',
                expected_auth=[AuthType.ADMIN],
                path_params={'runner_id': 'test-runner-id'}
            ),
            EndpointTest(
                method='DELETE',
                path='/api/runners/<runner_id>',
                description='Delete runner',
                expected_auth=[AuthType.ADMIN],
                path_params={'runner_id': 'test-runner-id'}
            ),
            EndpointTest(
                method='POST',
                path='/api/runners/<runner_id>/enable',
                description='Enable runner',
                expected_auth=[AuthType.ADMIN],
                path_params={'runner_id': 'test-runner-id'}
            ),
            EndpointTest(
                method='POST',
                path='/api/runners/<runner_id>/disable',
                description='Disable runner',
                expected_auth=[AuthType.ADMIN],
                path_params={'runner_id': 'test-runner-id'}
            ),

            # Enrollment (admin only to create, enrollment token to use)
            EndpointTest(
                method='POST',
                path='/api/enrollment/token',
                description='Create enrollment token',
                expected_auth=[AuthType.ADMIN],
                body={'runner_name': 'test-runner'}
            ),
            EndpointTest(
                method='POST',
                path='/api/enrollment/enroll',
                description='Enroll runner with token',
                expected_auth=[AuthType.ENROLLMENT],
                body={'runner_id': 'test-id', 'hostname': 'test-host', 'devices': [],
                     'api_key': 'test-key'}
            ),
            EndpointTest(
                method='GET',
                path='/api/enrollment/tokens',
                description='List enrollment tokens',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='DELETE',
                path='/api/enrollment/token/<token>',
                description='Delete enrollment token',
                expected_auth=[AuthType.ADMIN],
                path_params={'token': 'test-token'}
            ),
            EndpointTest(
                method='POST',
                path='/api/enrollment/re-enroll/<runner_id>',
                description='Re-enroll existing runner',
                expected_auth=[AuthType.ADMIN],
                path_params={'runner_id': 'test-runner-id'},
                body={'api_key': 'test-key'}
            ),

            # Provisioning API (provisioning key or admin)
            EndpointTest(
                method='POST',
                path='/api/provisioning/keys',
                description='Create provisioning API key',
                expected_auth=[AuthType.ADMIN],
                body={'name': 'test-key', 'description': 'Test key'}
            ),
            EndpointTest(
                method='GET',
                path='/api/provisioning/keys',
                description='List provisioning API keys',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='DELETE',
                path='/api/provisioning/keys/<key_id>',
                description='Delete provisioning API key',
                expected_auth=[AuthType.ADMIN],
                path_params={'key_id': '1'}
            ),
            EndpointTest(
                method='POST',
                path='/api/provisioning/keys/<key_id>/toggle',
                description='Toggle provisioning API key',
                expected_auth=[AuthType.ADMIN],
                path_params={'key_id': '1'}
            ),
            EndpointTest(
                method='POST',
                path='/api/provisioning/provision',
                description='Provision new runner',
                expected_auth=[AuthType.PROVISIONING, AuthType.ADMIN],
                body={'runner_name': 'test-runner'}
            ),

            # Challenge management (admin only)
            EndpointTest(
                method='GET',
                path='/api/challenges',
                description='List all challenges',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='POST',
                path='/api/challenges',
                description='Create challenge',
                expected_auth=[AuthType.ADMIN],
                body={'challenge_id': 'test-challenge', 'name': 'Test', 'type': 'static'}
            ),
            EndpointTest(
                method='GET',
                path='/api/challenges/<challenge_id>',
                description='Get challenge details',
                expected_auth=[AuthType.ADMIN],
                path_params={'challenge_id': 'test-challenge'}
            ),
            EndpointTest(
                method='PUT',
                path='/api/challenges/<challenge_id>',
                description='Update challenge',
                expected_auth=[AuthType.ADMIN],
                path_params={'challenge_id': 'test-challenge'},
                body={'name': 'Updated Test'}
            ),
            EndpointTest(
                method='DELETE',
                path='/api/challenges/<challenge_id>',
                description='Delete challenge',
                expected_auth=[AuthType.ADMIN],
                path_params={'challenge_id': 'test-challenge'}
            ),
            EndpointTest(
                method='POST',
                path='/api/challenges/<challenge_id>/enable',
                description='Enable challenge',
                expected_auth=[AuthType.ADMIN],
                path_params={'challenge_id': 'test-challenge'}
            ),
            EndpointTest(
                method='POST',
                path='/api/challenges/<challenge_id>/trigger',
                description='Trigger challenge',
                expected_auth=[AuthType.ADMIN],
                path_params={'challenge_id': 'test-challenge'}
            ),
            EndpointTest(
                method='POST',
                path='/api/challenges/reload',
                description='Reload challenges from disk',
                expected_auth=[AuthType.ADMIN]
            ),

            # Transmissions (admin only)
            EndpointTest(
                method='GET',
                path='/api/transmissions',
                description='Get transmission log',
                expected_auth=[AuthType.ADMIN]
            ),

            # Control (admin only)
            EndpointTest(
                method='POST',
                path='/api/control/pause',
                description='Pause system',
                expected_auth=[AuthType.ADMIN]
            ),
            EndpointTest(
                method='POST',
                path='/api/control/resume',
                description='Resume system',
                expected_auth=[AuthType.ADMIN]
            ),

            # File operations (admin or runner)
            EndpointTest(
                method='GET',
                path='/api/files/<file_hash>',
                description='Download file',
                expected_auth=[AuthType.ADMIN, AuthType.RUNNER],
                path_params={'file_hash': 'test-hash'}
            ),
        ]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Audit API authentication for ChallengeCtl',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--url', help='Base URL of the API server',
                       default=os.environ.get('AUDIT_URL', 'http://localhost:5000'))
    parser.add_argument('--admin-username', help='Admin username',
                       default=os.environ.get('AUDIT_ADMIN_USERNAME'))
    parser.add_argument('--admin-password', help='Admin password',
                       default=os.environ.get('AUDIT_ADMIN_PASSWORD'))
    parser.add_argument('--admin-totp-secret', help='Admin TOTP secret',
                       default=os.environ.get('AUDIT_ADMIN_TOTP_SECRET'))
    parser.add_argument('--runner-api-key', help='Runner API key',
                       default=os.environ.get('AUDIT_RUNNER_API_KEY'))
    parser.add_argument('--provisioning-api-key', help='Provisioning API key',
                       default=os.environ.get('AUDIT_PROVISIONING_API_KEY'))
    parser.add_argument('--enrollment-token', help='Enrollment token',
                       default=os.environ.get('AUDIT_ENROLLMENT_TOKEN'))

    args = parser.parse_args()

    # Create auditor
    auditor = APIAuthAuditor(
        base_url=args.url,
        admin_username=args.admin_username,
        admin_password=args.admin_password,
        admin_totp_secret=args.admin_totp_secret,
        runner_api_key=args.runner_api_key,
        provisioning_api_key=args.provisioning_api_key,
        enrollment_token=args.enrollment_token
    )

    # Run audit
    exit_code = auditor.run_audit()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
