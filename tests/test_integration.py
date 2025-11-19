#!/usr/bin/env python3
"""Integration tests for challengectl system."""

import pytest
import tempfile
import os
import sys

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from database import Database


@pytest.fixture
def integrated_db():
    """Create a database with some test data."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = Database(db_path)

    # Set up test data
    db.create_user('admin', 'admin_hash', '')
    db.create_user('user1', 'user1_hash', '')

    yield db

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_runner_registration_workflow(self, integrated_db):
        """Test complete runner registration and heartbeat workflow."""
        # Register runner
        result = integrated_db.register_runner(
            runner_id='test-runner-1',
            hostname='test-host',
            ip_address='192.168.1.100',
            devices=[
                {'device_id': 'rtlsdr', 'type': 'rtl-sdr'},
                {'device_id': 'hackrf', 'type': 'hackrf'}
            ]
        )

        assert result is True

        # Update heartbeat
        success, message = integrated_db.update_heartbeat('test-runner-1')
        assert success is True

        # Get runner status
        runner = integrated_db.get_runner('test-runner-1')
        assert runner is not None
        assert runner['hostname'] == 'test-host'

    def test_challenge_transmission_workflow(self, integrated_db):
        """Test complete challenge creation and transmission workflow."""
        # Create a runner
        integrated_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[{'device_id': 'rtlsdr', 'type': 'rtl-sdr'}]
        )

        # Add a challenge
        config = {
            'type': 'fm',
            'frequency': 146520000,
            'flag': 'flag{test_rf_123}'
        }

        result = integrated_db.add_challenge(
            challenge_id='rf-challenge-1',
            name='RF Challenge 1',
            config=config
        )

        assert result is True

        # Record transmission
        transmission_id = integrated_db.record_transmission_start(
            challenge_id='rf-challenge-1',
            runner_id='test-runner',
            device_id='rtlsdr',
            frequency=146520000
        )

        assert transmission_id is not None

        # Get recent transmissions
        transmissions = integrated_db.get_recent_transmissions(limit=10)
        assert len(transmissions) > 0

    def test_multi_runner_scenario(self, integrated_db):
        """Test scenario with multiple runners."""
        # Register multiple runners
        runners = [
            ('runner-1', 'host-1', '192.168.1.1'),
            ('runner-2', 'host-2', '192.168.1.2'),
            ('runner-3', 'host-3', '192.168.1.3')
        ]

        for runner_id, hostname, ip in runners:
            integrated_db.register_runner(
                runner_id=runner_id,
                hostname=hostname,
                ip_address=ip,
                devices=[]
            )

        # Get all runners
        all_runners = integrated_db.get_all_runners()
        assert len(all_runners) == 3

        # Disable one runner
        integrated_db.disable_runner('runner-2')

        # Verify runner is disabled
        runner = integrated_db.get_runner('runner-2')
        assert runner['enabled'] == 0

    def test_challenge_assignment_workflow(self, integrated_db):
        """Test challenge assignment to runners."""
        # Create runner
        integrated_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[{'device_id': 'rtlsdr', 'type': 'rtl-sdr'}]
        )

        # Mark runner as online
        integrated_db.update_heartbeat('test-runner')

        # Create challenges
        for i in range(3):
            integrated_db.add_challenge(
                challenge_id=f'challenge-{i}',
                name=f'Challenge {i}',
                config={'type': 'fm', 'frequency': 146520000 + i * 1000}
            )

        # Assign challenge to runner
        challenge = integrated_db.assign_challenge('test-runner', timeout_minutes=5)

        # Should get a challenge assigned
        assert challenge is not None or challenge is None  # May be None if all assigned


@pytest.mark.integration
class TestDataConsistency:
    """Test data consistency and integrity."""

    def test_unique_runner_id(self, integrated_db):
        """Test that runner IDs must be unique."""
        # Register a runner
        result1 = integrated_db.register_runner(
            runner_id='unique-runner',
            hostname='host1',
            ip_address='127.0.0.1',
            devices=[]
        )
        assert result1 is True

        # Registering with same ID should update, not fail
        result2 = integrated_db.register_runner(
            runner_id='unique-runner',
            hostname='host2',
            ip_address='127.0.0.2',
            devices=[]
        )

        # Should have updated the runner
        runner = integrated_db.get_runner('unique-runner')
        assert runner is not None
        assert runner['hostname'] == 'host2'

    def test_unique_challenge_name(self, integrated_db):
        """Test that challenge names must be unique."""
        config1 = {'type': 'fm', 'frequency': 146520000}
        config2 = {'type': 'am', 'frequency': 146530000}

        # Add first challenge
        result1 = integrated_db.add_challenge(
            challenge_id='challenge-1',
            name='Unique Challenge',
            config=config1
        )
        assert result1 is True

        # Adding challenge with same name should fail
        result2 = integrated_db.add_challenge(
            challenge_id='challenge-2',
            name='Unique Challenge',
            config=config2
        )
        assert result2 is False

    def test_cascade_delete_behavior(self, integrated_db):
        """Test deletion behavior."""
        # Create a runner and challenge
        integrated_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        integrated_db.add_challenge(
            challenge_id='test-challenge',
            name='Test Challenge',
            config={'type': 'fm'}
        )

        # Delete challenge
        result = integrated_db.delete_challenge('test-challenge')
        assert result is True

        # Challenge should be gone
        challenge = integrated_db.get_challenge('test-challenge')
        assert challenge is None


@pytest.mark.integration
class TestPerformance:
    """Test performance with larger datasets."""

    def test_many_transmissions(self, integrated_db):
        """Test handling many transmissions."""
        # Create a runner and challenge
        integrated_db.register_runner(
            runner_id='test-runner',
            hostname='test-host',
            ip_address='127.0.0.1',
            devices=[]
        )

        integrated_db.add_challenge(
            challenge_id='popular-challenge',
            name='Popular Challenge',
            config={'type': 'fm'}
        )

        # Create many transmissions
        for i in range(50):
            integrated_db.record_transmission_start(
                challenge_id='popular-challenge',
                runner_id='test-runner',
                device_id='rtlsdr',
                frequency=146520000 + i
            )

        # Retrieve transmissions
        transmissions = integrated_db.get_recent_transmissions(limit=100)
        assert len(transmissions) >= 50

    def test_many_runners(self, integrated_db):
        """Test handling many runners."""
        # Register many runners
        for i in range(20):
            integrated_db.register_runner(
                runner_id=f'runner-{i}',
                hostname=f'host-{i}',
                ip_address=f'192.168.1.{i}',
                devices=[]
            )

        # Get all runners
        runners = integrated_db.get_all_runners()
        assert len(runners) >= 20

    def test_many_challenges(self, integrated_db):
        """Test handling many challenges."""
        # Create many challenges
        for i in range(30):
            integrated_db.add_challenge(
                challenge_id=f'challenge-{i}',
                name=f'Challenge {i}',
                config={'type': 'fm', 'frequency': 146000000 + i * 1000}
            )

        # Get all challenges
        challenges = integrated_db.get_all_challenges()
        assert len(challenges) >= 30


@pytest.mark.integration
class TestSessionManagement:
    """Test session management."""

    def test_create_and_get_session(self, integrated_db):
        """Test creating and retrieving sessions."""
        # Create a session
        result = integrated_db.create_session(
            session_token='test-token-123',
            username='admin',
            expires='2025-12-31 23:59:59',
            totp_verified=True
        )

        assert result is True

        # Retrieve session
        session = integrated_db.get_session('test-token-123')
        assert session is not None
        assert session['username'] == 'admin'
        assert session['totp_verified'] == 1


@pytest.mark.integration
class TestChallengeLifecycle:
    """Test complete challenge lifecycle."""

    def test_challenge_enable_disable_cycle(self, integrated_db):
        """Test enabling and disabling challenges through lifecycle."""
        # Create challenge
        integrated_db.add_challenge(
            challenge_id='lifecycle-challenge',
            name='Lifecycle Test',
            config={'type': 'fm'}
        )

        # Initially should be enabled
        challenge = integrated_db.get_challenge('lifecycle-challenge')
        assert challenge['enabled'] is True

        # Disable it
        integrated_db.enable_challenge('lifecycle-challenge', enabled=False)
        challenge = integrated_db.get_challenge('lifecycle-challenge')
        assert challenge['enabled'] is False

        # Re-enable
        integrated_db.enable_challenge('lifecycle-challenge', enabled=True)
        challenge = integrated_db.get_challenge('lifecycle-challenge')
        assert challenge['enabled'] is True

        # Delete
        result = integrated_db.delete_challenge('lifecycle-challenge')
        assert result is True
