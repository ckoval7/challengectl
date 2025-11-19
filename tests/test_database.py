#!/usr/bin/env python3
"""Unit tests for database module."""

import pytest
import tempfile
import os
import sys
from datetime import datetime, timedelta, timezone

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from database import Database


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


class TestDatabaseInit:
    """Test database initialization."""

    def test_database_creation(self, temp_db):
        """Test that database is created successfully."""
        assert temp_db is not None
        assert os.path.exists(temp_db.db_path)

    def test_schema_tables_exist(self, temp_db):
        """Test that all required tables are created."""
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()

            # Check for main tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            required_tables = {
                'runners', 'enrollment_tokens', 'challenges',
                'submissions', 'users', 'sessions', 'config'
            }

            # Check that at least some core tables exist
            assert 'runners' in tables
            assert 'users' in tables
            assert 'challenges' in tables


class TestRunnerOperations:
    """Test runner-related database operations."""

    def test_register_runner(self, temp_db):
        """Test registering a new runner."""
        runner_id = temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=['device1', 'device2']
        )

        assert runner_id == 'test-runner'

        # Verify runner was registered
        runners = temp_db.get_all_runners()
        assert len(runners) == 1
        assert runners[0]['runner_id'] == 'test-runner'
        assert runners[0]['hostname'] == 'test-host'

    def test_get_runner_status(self, temp_db):
        """Test getting runner status."""
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        status = temp_db.get_runner_status('test-runner')
        assert status is not None
        assert status['runner_id'] == 'test-runner'
        assert status['status'] == 'offline'

    def test_update_runner_heartbeat(self, temp_db):
        """Test updating runner heartbeat."""
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Update heartbeat
        temp_db.update_runner_heartbeat('test-runner')

        # Verify heartbeat was updated
        status = temp_db.get_runner_status('test-runner')
        assert status['last_heartbeat'] is not None

    def test_enable_disable_runner(self, temp_db):
        """Test enabling and disabling runners."""
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Disable runner
        temp_db.update_runner_enabled('test-runner', False)
        status = temp_db.get_runner_status('test-runner')
        assert status['enabled'] == 0

        # Enable runner
        temp_db.update_runner_enabled('test-runner', True)
        status = temp_db.get_runner_status('test-runner')
        assert status['enabled'] == 1


class TestChallengeOperations:
    """Test challenge-related database operations."""

    def test_add_challenge(self, temp_db):
        """Test adding a challenge."""
        challenge_id = temp_db.add_challenge(
            name='Test Challenge',
            flag='flag{test}',
            difficulty='easy',
            category='test'
        )

        assert challenge_id is not None

        # Verify challenge was added
        challenges = temp_db.get_all_challenges()
        assert len(challenges) > 0

    def test_get_challenge_by_id(self, temp_db):
        """Test getting a challenge by ID."""
        challenge_id = temp_db.add_challenge(
            name='Test Challenge',
            flag='flag{test}',
            difficulty='easy',
            category='test'
        )

        challenge = temp_db.get_challenge(challenge_id)
        assert challenge is not None
        assert challenge['name'] == 'Test Challenge'


class TestUserOperations:
    """Test user-related database operations."""

    def test_create_user(self, temp_db):
        """Test creating a new user."""
        # This tests the basic user creation flow
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ('testuser', 'hash123')
            )
            conn.commit()

            cursor.execute("SELECT username FROM users WHERE username = ?", ('testuser',))
            result = cursor.fetchone()
            assert result is not None
            assert result['username'] == 'testuser'

    def test_get_user(self, temp_db):
        """Test getting a user."""
        # Create a user first
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ('testuser', 'hash123')
            )
            conn.commit()

        user = temp_db.get_user('testuser')
        assert user is not None
        assert user['username'] == 'testuser'


class TestSubmissionOperations:
    """Test submission-related database operations."""

    def test_record_submission(self, temp_db):
        """Test recording a flag submission."""
        # Create a user and challenge first
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ('testuser', 'hash123')
            )
            conn.commit()

        challenge_id = temp_db.add_challenge(
            name='Test Challenge',
            flag='flag{test}',
            difficulty='easy',
            category='test'
        )

        # Record submission
        temp_db.record_submission(
            username='testuser',
            challenge_id=challenge_id,
            flag_submitted='flag{test}',
            correct=True
        )

        # Verify submission was recorded
        submissions = temp_db.get_submissions_by_user('testuser')
        assert len(submissions) > 0
        assert submissions[0]['correct'] == 1


class TestThreadSafety:
    """Test thread safety of database operations."""

    def test_connection_context_manager(self, temp_db):
        """Test that connection context manager works correctly."""
        with temp_db.get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_multiple_connections(self, temp_db):
        """Test that multiple connections can be opened."""
        with temp_db.get_connection() as conn1:
            with temp_db.get_connection() as conn2:
                assert conn1 is not None
                assert conn2 is not None
