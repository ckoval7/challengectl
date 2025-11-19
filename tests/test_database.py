#!/usr/bin/env python3
"""Unit tests for database module."""

import pytest
import tempfile
import os
import sys
import json
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

            # Check that core tables exist
            assert 'runners' in tables
            assert 'users' in tables
            assert 'challenges' in tables
            assert 'transmissions' in tables
            assert 'sessions' in tables
            assert 'enrollment_tokens' in tables


class TestRunnerOperations:
    """Test runner-related database operations."""

    def test_register_runner(self, temp_db):
        """Test registering a new runner."""
        result = temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[{'device_id': 'rtlsdr', 'type': 'rtl-sdr'}]
        )

        # register_runner returns True on success
        assert result is True

        # Verify runner was registered
        runners = temp_db.get_all_runners()
        assert len(runners) == 1
        assert runners[0]['runner_id'] == 'test-runner'
        assert runners[0]['hostname'] == 'test-host'

    def test_get_runner(self, temp_db):
        """Test getting runner information."""
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        runner = temp_db.get_runner('test-runner')
        assert runner is not None
        assert runner['runner_id'] == 'test-runner'
        assert runner['status'] == 'offline'

    def test_update_heartbeat(self, temp_db):
        """Test updating runner heartbeat."""
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Update heartbeat
        success, message = temp_db.update_heartbeat('test-runner')
        assert success is True

        # Verify heartbeat was updated
        runner = temp_db.get_runner('test-runner')
        assert runner['last_heartbeat'] is not None

    def test_enable_disable_runner(self, temp_db):
        """Test enabling and disabling runners."""
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Disable runner
        result = temp_db.disable_runner('test-runner')
        assert result is True
        runner = temp_db.get_runner('test-runner')
        assert runner['enabled'] == 0

        # Enable runner
        result = temp_db.enable_runner('test-runner')
        assert result is True
        runner = temp_db.get_runner('test-runner')
        assert runner['enabled'] == 1

    def test_mark_runner_offline(self, temp_db):
        """Test marking runner as offline."""
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        result = temp_db.mark_runner_offline('test-runner')
        assert result is True

        runner = temp_db.get_runner('test-runner')
        assert runner['status'] == 'offline'


class TestChallengeOperations:
    """Test challenge-related database operations."""

    def test_add_challenge(self, temp_db):
        """Test adding a challenge."""
        config = {
            'type': 'fm',
            'frequency': 146520000,
            'modulation': 'FM',
            'flag': 'flag{test}'
        }

        result = temp_db.add_challenge(
            challenge_id='test-challenge-1',
            name='Test FM Challenge',
            config=config
        )

        assert result is True

        # Verify challenge was added
        challenges = temp_db.get_all_challenges()
        assert len(challenges) > 0

    def test_get_challenge_by_id(self, temp_db):
        """Test getting a challenge by ID."""
        config = {'type': 'fm', 'flag': 'flag{test}'}

        temp_db.add_challenge(
            challenge_id='test-challenge-1',
            name='Test Challenge',
            config=config
        )

        challenge = temp_db.get_challenge('test-challenge-1')
        assert challenge is not None
        assert challenge['name'] == 'Test Challenge'
        assert challenge['config']['type'] == 'fm'

    def test_enable_disable_challenge(self, temp_db):
        """Test enabling and disabling challenges."""
        config = {'type': 'fm'}

        temp_db.add_challenge(
            challenge_id='test-challenge-1',
            name='Test Challenge',
            config=config
        )

        # Disable challenge
        result = temp_db.enable_challenge('test-challenge-1', enabled=False)
        assert result is True

        challenge = temp_db.get_challenge('test-challenge-1')
        assert challenge['enabled'] is False

        # Enable challenge
        result = temp_db.enable_challenge('test-challenge-1', enabled=True)
        assert result is True

        challenge = temp_db.get_challenge('test-challenge-1')
        assert challenge['enabled'] is True

    def test_delete_challenge(self, temp_db):
        """Test deleting a challenge."""
        config = {'type': 'fm'}

        temp_db.add_challenge(
            challenge_id='test-challenge-1',
            name='Test Challenge',
            config=config
        )

        # Delete the challenge
        result = temp_db.delete_challenge('test-challenge-1')
        assert result is True

        # Verify it's deleted
        challenge = temp_db.get_challenge('test-challenge-1')
        assert challenge is None


class TestUserOperations:
    """Test user-related database operations."""

    def test_create_user(self, temp_db):
        """Test creating a new user."""
        result = temp_db.create_user(
            username='testuser',
            password_hash='hash123',
            totp_secret=''
        )

        assert result is True

        user = temp_db.get_user('testuser')
        assert user is not None
        assert user['username'] == 'testuser'

    def test_get_user(self, temp_db):
        """Test getting a user."""
        temp_db.create_user('testuser', 'hash123', '')

        user = temp_db.get_user('testuser')
        assert user is not None
        assert user['username'] == 'testuser'
        assert user['password_hash'] == 'hash123'

    def test_disable_enable_user(self, temp_db):
        """Test disabling and enabling users."""
        temp_db.create_user('testuser', 'hash123', '')

        # Disable user
        result = temp_db.disable_user('testuser')
        assert result is True

        user = temp_db.get_user('testuser')
        assert user['enabled'] == 0

        # Enable user
        result = temp_db.enable_user('testuser')
        assert result is True

        user = temp_db.get_user('testuser')
        assert user['enabled'] == 1

    def test_change_password(self, temp_db):
        """Test changing user password."""
        temp_db.create_user('testuser', 'oldhash', '')

        result = temp_db.change_password('testuser', 'newhash')
        assert result is True

        user = temp_db.get_user('testuser')
        assert user['password_hash'] == 'newhash'

    def test_delete_user(self, temp_db):
        """Test deleting a user."""
        temp_db.create_user('testuser', 'hash123', '')

        result = temp_db.delete_user('testuser')
        assert result is True

        user = temp_db.get_user('testuser')
        assert user is None


class TestTransmissionOperations:
    """Test transmission-related database operations."""

    def test_record_transmission_start(self, temp_db):
        """Test recording transmission start."""
        # Create a runner and challenge first
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        temp_db.add_challenge(
            challenge_id='test-challenge',
            name='Test Challenge',
            config={'type': 'fm'}
        )

        # Record transmission start
        transmission_id = temp_db.record_transmission_start(
            challenge_id='test-challenge',
            runner_id='test-runner',
            device_id='rtlsdr',
            frequency=146520000
        )

        assert transmission_id is not None
        assert transmission_id > 0

    def test_get_recent_transmissions(self, temp_db):
        """Test getting recent transmissions."""
        # Create test data
        temp_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        temp_db.add_challenge(
            challenge_id='test-challenge',
            name='Test Challenge',
            config={'type': 'fm'}
        )

        # Record a transmission
        temp_db.record_transmission_start(
            challenge_id='test-challenge',
            runner_id='test-runner',
            device_id='rtlsdr',
            frequency=146520000
        )

        # Get recent transmissions
        transmissions = temp_db.get_recent_transmissions(limit=10)
        assert len(transmissions) > 0


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
                # They should be the same thread-local connection
                assert conn1 is conn2


class TestSystemState:
    """Test system state operations."""

    def test_set_get_system_state(self, temp_db):
        """Test setting and getting system state."""
        temp_db.set_system_state('test_key', 'test_value')

        value = temp_db.get_system_state('test_key')
        assert value == 'test_value'

    def test_get_system_state_default(self, temp_db):
        """Test getting system state with default value."""
        value = temp_db.get_system_state('nonexistent_key', default='default')
        assert value == 'default'
