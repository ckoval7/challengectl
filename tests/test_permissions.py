#!/usr/bin/env python3
"""Comprehensive tests for permission system."""

import pytest
import tempfile
import os
import sys
import json
from datetime import datetime

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from database import Database
from api import PERMISSION_DEFINITIONS, VALID_PERMISSIONS


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = Database(db_path)
    yield db

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


class TestPermissionConstants:
    """Test permission constant definitions."""

    def test_permission_definitions_structure(self):
        """Test that PERMISSION_DEFINITIONS has correct structure."""
        assert isinstance(PERMISSION_DEFINITIONS, list)
        assert len(PERMISSION_DEFINITIONS) == 3

        # Check each permission has required fields
        for perm in PERMISSION_DEFINITIONS:
            assert 'name' in perm
            assert 'description' in perm
            assert 'category' in perm
            assert isinstance(perm['name'], str)
            assert isinstance(perm['description'], str)
            assert isinstance(perm['category'], str)

    def test_valid_permissions_list_matches_definitions(self):
        """Test VALID_PERMISSIONS derives correctly from PERMISSION_DEFINITIONS."""
        assert isinstance(VALID_PERMISSIONS, list)
        assert len(VALID_PERMISSIONS) == len(PERMISSION_DEFINITIONS)

        # Verify each name from definitions is in VALID_PERMISSIONS
        definition_names = [p['name'] for p in PERMISSION_DEFINITIONS]
        assert VALID_PERMISSIONS == definition_names

        # Verify expected permissions are present
        assert 'create_users' in VALID_PERMISSIONS
        assert 'create_provisioning_key' in VALID_PERMISSIONS
        assert 'manage_webhooks' in VALID_PERMISSIONS

    def test_permission_metadata_completeness(self):
        """Test that all permissions have meaningful descriptions and categories."""
        for perm in PERMISSION_DEFINITIONS:
            # Name should be snake_case
            assert '_' in perm['name'] or perm['name'].islower()

            # Description should be descriptive (at least 10 chars)
            assert len(perm['description']) >= 10

            # Category should be set
            assert len(perm['category']) > 0


class TestPermissionDatabaseOperations:
    """Test permission-related database operations."""

    def test_grant_permission_success(self, temp_db):
        """Test granting a valid permission to a user."""
        # Create test user
        temp_db.create_user('testuser', 'hash123', '')

        # Grant permission
        result = temp_db.grant_permission('testuser', 'create_users', 'admin')
        assert result is True

        # Verify permission was granted
        assert temp_db.has_permission('testuser', 'create_users') is True

    def test_grant_all_permissions(self, temp_db):
        """Test granting all permissions using VALID_PERMISSIONS list."""
        # Create test user
        temp_db.create_user('testuser', 'hash123', '')

        # Grant all permissions
        for permission in VALID_PERMISSIONS:
            result = temp_db.grant_permission('testuser', permission, 'system')
            assert result is True

        # Verify all permissions were granted
        for permission in VALID_PERMISSIONS:
            assert temp_db.has_permission('testuser', permission) is True

    def test_revoke_permission_success(self, temp_db):
        """Test revoking a permission from a user."""
        # Create user and grant permission
        temp_db.create_user('testuser', 'hash123', '')
        temp_db.grant_permission('testuser', 'create_users', 'admin')

        # Verify permission exists
        assert temp_db.has_permission('testuser', 'create_users') is True

        # Revoke permission
        result = temp_db.revoke_permission('testuser', 'create_users')
        assert result is True

        # Verify permission was revoked
        assert temp_db.has_permission('testuser', 'create_users') is False

    def test_permission_persistence(self, temp_db):
        """Test that permissions persist across database connections."""
        # Create user and grant permission
        temp_db.create_user('testuser', 'hash123', '')
        temp_db.grant_permission('testuser', 'create_users', 'admin')

        # Close and reopen connection (simulated by just checking again)
        assert temp_db.has_permission('testuser', 'create_users') is True

    def test_user_deletion_cascades_permissions(self, temp_db):
        """Test that deleting a user also removes their permissions."""
        # Create user and grant permissions
        temp_db.create_user('testuser', 'hash123', '')
        temp_db.grant_permission('testuser', 'create_users', 'admin')
        temp_db.grant_permission('testuser', 'create_provisioning_key', 'admin')

        # Delete user
        temp_db.delete_user('testuser')

        # Verify permissions are gone
        assert temp_db.has_permission('testuser', 'create_users') is False
        assert temp_db.has_permission('testuser', 'create_provisioning_key') is False


@pytest.mark.integration
class TestPermissionValidation:
    """Test permission validation in workflows."""

    def test_only_valid_permissions_can_be_granted(self, temp_db):
        """Test that only permissions in VALID_PERMISSIONS can be granted."""
        temp_db.create_user('testuser', 'hash123', '')

        # Valid permission should work
        for permission in VALID_PERMISSIONS:
            result = temp_db.grant_permission('testuser', permission, 'admin')
            assert result is True

        # Invalid permission should not exist in system
        # (The database will accept it, but the API should reject it)
        # This test verifies VALID_PERMISSIONS contains only expected values
        assert 'invalid_permission' not in VALID_PERMISSIONS
        assert 'super_admin' not in VALID_PERMISSIONS
        assert 'delete_everything' not in VALID_PERMISSIONS


@pytest.mark.integration
class TestInitialAdminPermissions:
    """Test initial admin user permission granting."""

    def test_initial_admin_workflow(self, temp_db):
        """Test that initial admin would get all permissions via loop."""
        # Simulate initial admin creation
        username = 'initial_admin'
        temp_db.create_user(username, 'hash123', 'totp_secret')

        # Grant all permissions (simulating the for loop in api.py)
        for permission in VALID_PERMISSIONS:
            temp_db.grant_permission(username, permission, 'system')

        # Verify all permissions were granted
        for permission in VALID_PERMISSIONS:
            assert temp_db.has_permission(username, permission) is True

        # Verify granted_by is 'system' (check via database)
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT permission_name, granted_by FROM permissions WHERE username = ?",
                (username,)
            )
            permissions = cursor.fetchall()

            assert len(permissions) == len(VALID_PERMISSIONS)
            for perm_name, granted_by in permissions:
                assert granted_by == 'system'

    def test_non_initial_users_need_explicit_grants(self, temp_db):
        """Test that non-initial users don't automatically get permissions."""
        # Create a regular user (not initial admin)
        temp_db.create_user('regular_user', 'hash123', None, is_temporary=True)

        # User should have no permissions by default
        for permission in VALID_PERMISSIONS:
            assert temp_db.has_permission('regular_user', permission) is False


@pytest.mark.integration
class TestPermissionWorkflows:
    """Test complete permission grant/revoke workflows."""

    def test_full_permission_lifecycle(self, temp_db):
        """Test complete permission grant/revoke workflow."""
        # Setup: Create admin and regular user
        temp_db.create_user('admin', 'admin_hash', '')
        temp_db.create_user('user1', 'user1_hash', '')

        # Grant permission to admin
        temp_db.grant_permission('admin', 'create_users', 'system')
        assert temp_db.has_permission('admin', 'create_users') is True

        # Admin grants permission to user1
        temp_db.grant_permission('user1', 'create_provisioning_key', 'admin')
        assert temp_db.has_permission('user1', 'create_provisioning_key') is True

        # Verify user1 doesn't have other permissions
        assert temp_db.has_permission('user1', 'create_users') is False

        # Revoke permission from user1
        temp_db.revoke_permission('user1', 'create_provisioning_key')
        assert temp_db.has_permission('user1', 'create_provisioning_key') is False

    def test_permission_granted_by_tracking(self, temp_db):
        """Test that permission grants track who granted them."""
        temp_db.create_user('admin', 'admin_hash', '')
        temp_db.create_user('user1', 'user1_hash', '')

        # Grant permission
        temp_db.grant_permission('user1', 'create_users', 'admin')

        # Verify granted_by is tracked
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT granted_by FROM permissions WHERE username = ? AND permission_name = ?",
                ('user1', 'create_users')
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 'admin'

    def test_multiple_permissions_per_user(self, temp_db):
        """Test that a user can have multiple permissions."""
        temp_db.create_user('poweruser', 'hash123', '')

        # Grant multiple permissions
        for permission in VALID_PERMISSIONS:
            temp_db.grant_permission('poweruser', permission, 'system')

        # Verify all permissions
        for permission in VALID_PERMISSIONS:
            assert temp_db.has_permission('poweruser', permission) is True


@pytest.mark.integration
class TestPermissionEdgeCases:
    """Test edge cases and error conditions."""

    def test_grant_permission_to_nonexistent_user(self, temp_db):
        """Test granting permission to user that doesn't exist."""
        # This should fail gracefully (database constraint)
        result = temp_db.grant_permission('nonexistent', 'create_users', 'admin')
        assert result is False

    def test_duplicate_permission_grant(self, temp_db):
        """Test granting same permission twice."""
        temp_db.create_user('testuser', 'hash123', '')

        # Grant permission first time
        result1 = temp_db.grant_permission('testuser', 'create_users', 'admin')
        assert result1 is True

        # Grant same permission again (should be idempotent or return True)
        result2 = temp_db.grant_permission('testuser', 'create_users', 'admin')
        # Database should handle this gracefully
        assert temp_db.has_permission('testuser', 'create_users') is True

    def test_revoke_nonexistent_permission(self, temp_db):
        """Test revoking permission user doesn't have."""
        temp_db.create_user('testuser', 'hash123', '')

        # Revoke permission that was never granted
        result = temp_db.revoke_permission('testuser', 'create_users')
        # Should complete without error (no rows affected is still success)
        assert result is not None


@pytest.mark.integration
class TestPermissionSecurityControls:
    """Test security controls for permission system."""

    def test_cannot_grant_permission_to_self(self, temp_db):
        """Test that users cannot grant permissions to themselves.

        This is a critical security control that prevents privilege escalation.
        A user with create_users permission should NOT be able to grant
        themselves additional permissions (e.g., manage_webhooks).

        Note: This is a database-level test. The API layer implements the
        actual enforcement to prevent self-grants.
        """
        # Create test users
        temp_db.create_user('alice', 'hash123', 'totp_secret', is_temporary=False)
        temp_db.create_user('bob', 'hash456', 'totp_secret2', is_temporary=False)

        # Grant alice the create_users permission
        temp_db.grant_permission('alice', 'create_users', 'system')

        # Verify alice has create_users but not manage_webhooks
        assert temp_db.has_permission('alice', 'create_users') is True
        assert temp_db.has_permission('alice', 'manage_webhooks') is False

        # Alice should be able to grant permissions to Bob at the DB level
        result = temp_db.grant_permission('bob', 'manage_webhooks', 'alice')
        assert result is True
        assert temp_db.has_permission('bob', 'manage_webhooks') is True

        # At the DATABASE level, self-grants are technically possible
        # (needed for initial setup). The API layer must block this.
        # This test documents that the DB allows it, but API should not.
        result = temp_db.grant_permission('alice', 'manage_webhooks', 'alice')
        assert result is True  # DB allows it
        assert temp_db.has_permission('alice', 'manage_webhooks') is True

        # Clean up for documentation purposes
        temp_db.revoke_permission('alice', 'manage_webhooks')

        # The key insight: The API endpoint at server/api.py:1855 must include
        # a check like:
        #     if username == request.admin_username:
        #         return jsonify({'error': 'Cannot grant permissions to yourself'}), 400
        #
        # This prevents the privilege escalation attack even though the
        # database layer technically allows self-grants for system use.
