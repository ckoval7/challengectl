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
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Create test users
        cursor.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            ('admin', 'admin_hash', 1)
        )
        cursor.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            ('player1', 'player1_hash', 0)
        )
        conn.commit()

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
        runner_id = integrated_db.register_runner(
            runner_id='test-runner-1',
            hostname='test-host',
            ip_address='192.168.1.100',
            devices=['rtlsdr', 'hackrf']
        )

        assert runner_id is not None

        # Update heartbeat
        integrated_db.update_runner_heartbeat(runner_id)

        # Get runner status
        status = integrated_db.get_runner_status(runner_id)
        assert status['status'] == 'online' or status['status'] == 'offline'
        assert status['hostname'] == 'test-host'
        assert 'rtlsdr' in str(status['devices'])

    def test_challenge_submission_workflow(self, integrated_db):
        """Test complete challenge creation and submission workflow."""
        # Add a challenge
        challenge_id = integrated_db.add_challenge(
            name='RF Challenge 1',
            flag='flag{test_rf_123}',
            difficulty='medium',
            category='rf'
        )

        assert challenge_id is not None

        # Submit correct flag
        integrated_db.record_submission(
            username='player1',
            challenge_id=challenge_id,
            flag_submitted='flag{test_rf_123}',
            correct=True
        )

        # Check submissions
        submissions = integrated_db.get_submissions_by_user('player1')
        assert len(submissions) > 0
        assert submissions[0]['correct'] == 1

        # Submit incorrect flag
        integrated_db.record_submission(
            username='player1',
            challenge_id=challenge_id,
            flag_submitted='flag{wrong}',
            correct=False
        )

        # Check both submissions exist
        submissions = integrated_db.get_submissions_by_user('player1')
        assert len(submissions) >= 2

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
        integrated_db.update_runner_enabled('runner-2', False)

        # Verify runner is disabled
        status = integrated_db.get_runner_status('runner-2')
        assert status['enabled'] == 0

    def test_scoreboard_calculation(self, integrated_db):
        """Test scoreboard calculation with multiple submissions."""
        # Create challenges with different point values
        challenge1 = integrated_db.add_challenge(
            name='Easy Challenge',
            flag='flag{easy}',
            difficulty='easy',
            category='test'
        )

        challenge2 = integrated_db.add_challenge(
            name='Hard Challenge',
            flag='flag{hard}',
            difficulty='hard',
            category='test'
        )

        # Player1 solves both
        integrated_db.record_submission(
            username='player1',
            challenge_id=challenge1,
            flag_submitted='flag{easy}',
            correct=True
        )

        integrated_db.record_submission(
            username='player1',
            challenge_id=challenge2,
            flag_submitted='flag{hard}',
            correct=True
        )

        # Get submissions
        submissions = integrated_db.get_submissions_by_user('player1')
        correct_submissions = [s for s in submissions if s['correct'] == 1]

        assert len(correct_submissions) >= 2


@pytest.mark.integration
class TestDataConsistency:
    """Test data consistency and integrity."""

    def test_unique_constraints(self, integrated_db):
        """Test that unique constraints are enforced."""
        # Register a runner
        integrated_db.register_runner(
            runner_id='unique-runner',
            hostname='host',
            ip_address='127.0.0.1',
            devices=[]
        )

        # Attempting to register the same runner should update, not create duplicate
        integrated_db.register_runner(
            runner_id='unique-runner',
            hostname='new-host',
            ip_address='127.0.0.2',
            devices=[]
        )

        # Should only have one runner with this ID
        status = integrated_db.get_runner_status('unique-runner')
        assert status is not None
        # The hostname should be updated to the new value
        assert status['hostname'] == 'new-host'

    def test_foreign_key_integrity(self, integrated_db):
        """Test foreign key relationships."""
        # Create a challenge
        challenge_id = integrated_db.add_challenge(
            name='Test Challenge',
            flag='flag{test}',
            difficulty='easy',
            category='test'
        )

        # Record submission for existing user
        integrated_db.record_submission(
            username='player1',
            challenge_id=challenge_id,
            flag_submitted='flag{test}',
            correct=True
        )

        # Verify submission exists
        submissions = integrated_db.get_submissions_by_user('player1')
        assert len(submissions) > 0


@pytest.mark.integration
class TestPerformance:
    """Test performance with larger datasets."""

    def test_many_submissions(self, integrated_db):
        """Test handling many submissions."""
        # Create a challenge
        challenge_id = integrated_db.add_challenge(
            name='Popular Challenge',
            flag='flag{popular}',
            difficulty='easy',
            category='test'
        )

        # Create many submissions (simulate activity)
        for i in range(50):
            integrated_db.record_submission(
                username='player1',
                challenge_id=challenge_id,
                flag_submitted=f'flag{{attempt_{i}}}',
                correct=(i == 25)  # Only one correct submission
            )

        # Retrieve submissions
        submissions = integrated_db.get_submissions_by_user('player1')
        assert len(submissions) >= 50

        correct = [s for s in submissions if s['correct'] == 1]
        assert len(correct) >= 1

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
