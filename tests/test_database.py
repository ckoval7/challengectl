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
            assert 'agents' in tables
            assert 'users' in tables
            assert 'challenges' in tables
            assert 'transmissions' in tables
            assert 'sessions' in tables
            assert 'enrollment_tokens' in tables
            assert 'listener_assignments' in tables


class TestAgentOperations:
    """Test agent-related database operations (runners and listeners)."""

    def test_register_runner_agent(self, temp_db):
        """Test registering a new runner agent."""
        result = temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[{'device_id': '0', 'model': 'rtl-sdr'}]
        )

        # register_agent returns True on success
        assert result is True

        # Verify runner was registered
        agents = temp_db.get_all_agents(agent_type='runner')
        assert len(agents) == 1
        assert agents[0]['agent_id'] == 'test-runner'
        assert agents[0]['agent_type'] == 'runner'
        assert agents[0]['hostname'] == 'test-host'

    def test_register_listener_agent(self, temp_db):
        """Test registering a new listener agent."""
        result = temp_db.register_agent(
            agent_id='test-listener',
            agent_type='listener',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[{'device_id': '0', 'model': 'rtl-sdr'}]
        )

        assert result is True

        # Verify listener was registered
        agents = temp_db.get_all_agents(agent_type='listener')
        assert len(agents) == 1
        assert agents[0]['agent_id'] == 'test-listener'
        assert agents[0]['agent_type'] == 'listener'

    def test_get_agent(self, temp_db):
        """Test getting agent information."""
        temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        agent = temp_db.get_agent('test-runner')
        assert agent is not None
        assert agent['agent_id'] == 'test-runner'
        assert agent['agent_type'] == 'runner'
        assert agent['status'] == 'online'  # Agent is online when actively registering

    def test_update_agent_heartbeat(self, temp_db):
        """Test updating agent heartbeat."""
        temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Update heartbeat
        success, message = temp_db.update_agent_heartbeat('test-runner')
        assert success is True

        # Verify heartbeat was updated
        agent = temp_db.get_agent('test-runner')
        assert agent['last_heartbeat'] is not None

    def test_enable_disable_agent(self, temp_db):
        """Test enabling and disabling agents."""
        temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Disable agent
        result = temp_db.disable_agent('test-runner')
        assert result is True
        agent = temp_db.get_agent('test-runner')
        assert agent['enabled'] == 0

        # Enable agent
        result = temp_db.enable_agent('test-runner')
        assert result is True
        agent = temp_db.get_agent('test-runner')
        assert agent['enabled'] == 1

    def test_mark_agent_offline(self, temp_db):
        """Test marking agent as offline."""
        temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        result = temp_db.mark_agent_offline('test-runner')
        assert result is True

        agent = temp_db.get_agent('test-runner')
        assert agent['status'] == 'offline'

    def test_get_all_agents_filtered(self, temp_db):
        """Test filtering agents by type."""
        # Register a runner and a listener
        temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )
        temp_db.register_agent(
            agent_id='test-listener',
            agent_type='listener',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Get all agents
        all_agents = temp_db.get_all_agents()
        assert len(all_agents) == 2

        # Get only runners
        runners = temp_db.get_all_agents(agent_type='runner')
        assert len(runners) == 1
        assert runners[0]['agent_type'] == 'runner'

        # Get only listeners
        listeners = temp_db.get_all_agents(agent_type='listener')
        assert len(listeners) == 1
        assert listeners[0]['agent_type'] == 'listener'


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
        # Create a runner agent and challenge first
        temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
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
            agent_id='test-runner',
            device_id='0',
            frequency=146520000
        )

        assert transmission_id is not None
        assert transmission_id > 0

    def test_get_recent_transmissions(self, temp_db):
        """Test getting recent transmissions."""
        # Create test data
        temp_db.register_agent(
            agent_id='test-runner',
            agent_type='runner',
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
            agent_id='test-runner',
            device_id='0',
            frequency=146520000
        )

        # Get recent transmissions
        transmissions = temp_db.get_recent_transmissions(limit=10)
        assert len(transmissions) > 0


class TestListenerAssignments:
    """Test listener assignment operations."""

    def test_create_listener_assignment(self, temp_db):
        """Test creating a listener assignment."""
        # Create listener agent and challenge first
        temp_db.register_agent(
            agent_id='test-listener',
            agent_type='listener',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        temp_db.add_challenge(
            challenge_id='test-challenge',
            name='Test Challenge',
            config={'type': 'fm', 'frequency': 146520000}
        )

        # Create transmission first
        transmission_id = temp_db.record_transmission_start(
            challenge_id='test-challenge',
            agent_id='test-listener',
            device_id='0',
            frequency=146520000
        )

        # Create listener assignment
        expected_start = datetime.now(timezone.utc)
        assignment_id = temp_db.create_listener_assignment(
            agent_id='test-listener',
            challenge_id='test-challenge',
            transmission_id=transmission_id,
            frequency=146520000,
            expected_start=expected_start,
            expected_duration=30.0
        )

        assert assignment_id > 0

    def test_get_active_listener_assignments(self, temp_db):
        """Test getting active listener assignments."""
        # Create listener and challenge
        temp_db.register_agent(
            agent_id='test-listener',
            agent_type='listener',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        temp_db.add_challenge(
            challenge_id='test-challenge',
            name='Test Challenge',
            config={'type': 'fm', 'frequency': 146520000}
        )

        transmission_id = temp_db.record_transmission_start(
            challenge_id='test-challenge',
            agent_id='test-listener',
            device_id='0',
            frequency=146520000
        )

        # Create assignment
        expected_start = datetime.now(timezone.utc)
        temp_db.create_listener_assignment(
            agent_id='test-listener',
            challenge_id='test-challenge',
            transmission_id=transmission_id,
            frequency=146520000,
            expected_start=expected_start,
            expected_duration=30.0
        )

        # Get active assignments
        assignments = temp_db.get_active_listener_assignments('test-listener')
        assert len(assignments) == 1
        assert assignments[0]['agent_id'] == 'test-listener'
        assert assignments[0]['status'] == 'pending'

    def test_update_listener_assignment_status(self, temp_db):
        """Test updating listener assignment status."""
        # Setup
        temp_db.register_agent(
            agent_id='test-listener',
            agent_type='listener',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        temp_db.add_challenge(
            challenge_id='test-challenge',
            name='Test Challenge',
            config={'type': 'fm'}
        )

        transmission_id = temp_db.record_transmission_start(
            challenge_id='test-challenge',
            agent_id='test-listener',
            device_id='0',
            frequency=146520000
        )

        assignment_id = temp_db.create_listener_assignment(
            agent_id='test-listener',
            challenge_id='test-challenge',
            transmission_id=transmission_id,
            frequency=146520000,
            expected_start=datetime.now(timezone.utc),
            expected_duration=30.0
        )

        # Update status to completed
        result = temp_db.update_listener_assignment_status(assignment_id, 'completed')
        assert result is True

        # Verify status was updated
        assignment = temp_db.get_listener_assignment(assignment_id)
        assert assignment['status'] == 'completed'
        assert assignment['completed_at'] is not None

    def test_cancel_listener_assignments_for_agent(self, temp_db):
        """Test cancelling all assignments for an agent."""
        # Setup
        temp_db.register_agent(
            agent_id='test-listener',
            agent_type='listener',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        temp_db.add_challenge(
            challenge_id='test-challenge',
            name='Test Challenge',
            config={'type': 'fm'}
        )

        transmission_id = temp_db.record_transmission_start(
            challenge_id='test-challenge',
            agent_id='test-listener',
            device_id='0',
            frequency=146520000
        )

        temp_db.create_listener_assignment(
            agent_id='test-listener',
            challenge_id='test-challenge',
            transmission_id=transmission_id,
            frequency=146520000,
            expected_start=datetime.now(timezone.utc),
            expected_duration=30.0
        )

        # Cancel all assignments
        count = temp_db.cancel_listener_assignments_for_agent('test-listener')
        assert count == 1

        # Verify no active assignments
        assignments = temp_db.get_active_listener_assignments('test-listener')
        assert len(assignments) == 0


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
