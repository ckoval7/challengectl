#!/usr/bin/env python3
"""
User management CLI for ChallengeCtl server.
Manages admin users with username/password/TOTP authentication.
"""

import argparse
import sys
import os
import getpass
import bcrypt
import pyotp
import qrcode
import yaml

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from database import Database
from crypto import encrypt_totp_secret


def load_config(config_path: str) -> dict:
    """Load server configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        print(f"Warning: Could not load config file {config_path}: {e}")
        return {}


def get_conference_name(config: dict) -> str:
    """Get the conference name from config."""
    return config.get('conference', {}).get('name', 'ChallengeCtl')


def create_user(db: Database, username: str, password: str = None, conference_name: str = "ChallengeCtl"):
    """Create a new admin user with TOTP secret."""
    # Check if user already exists
    existing_user = db.get_user(username)
    if existing_user:
        print(f"Error: User '{username}' already exists")
        return 1

    # Get password
    if not password:
        password = getpass.getpass("Enter password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            print("Error: Passwords do not match")
            return 1

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        return 1

    # Hash password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Generate TOTP secret
    totp_secret = pyotp.random_base32()

    # Create user
    if db.create_user(username, password_hash, totp_secret):
        print(f"\nUser '{username}' created successfully!")
        print(f"\nTOTP Secret: {totp_secret}")
        print("\nSetup TOTP in your authenticator app:")
        print("1. Scan the QR code below, OR")
        print("2. Manually enter the secret above")

        # Generate QR code
        totp = pyotp.TOTP(totp_secret)
        provisioning_uri = totp.provisioning_uri(name=username, issuer_name=conference_name)

        print("\n QR Code:")
        qr = qrcode.QRCode()
        qr.add_data(provisioning_uri)
        qr.print_ascii(invert=True)

        print(f"\nProvisioning URI: {provisioning_uri}")
        print("\nTest your TOTP code before logging in:")
        while True:
            test_code = input("Enter TOTP code (or 'skip' to continue): ").strip()
            if test_code.lower() == 'skip':
                break
            if totp.verify(test_code):
                print("✓ TOTP code is valid!")
                break
            else:
                print("✗ Invalid TOTP code. Try again.")

        return 0
    else:
        print(f"Error: Failed to create user '{username}'")
        return 1


def list_users(db: Database):
    """List all users."""
    users = db.get_all_users()

    if not users:
        print("No users found")
        return 0

    print(f"\n{'Username':<20} {'Enabled':<10} {'Created':<25} {'Last Login':<25}")
    print("-" * 80)

    for user in users:
        username = user['username']
        enabled = "Yes" if user['enabled'] else "No"
        created = user['created_at'] or "N/A"
        last_login = user['last_login'] or "Never"
        print(f"{username:<20} {enabled:<10} {created:<25} {last_login:<25}")

    return 0


def disable_user(db: Database, username: str):
    """Disable a user account."""
    if db.disable_user(username):
        print(f"User '{username}' disabled successfully")
        return 0
    else:
        print(f"Error: User '{username}' not found")
        return 1


def enable_user(db: Database, username: str):
    """Enable a user account."""
    if db.enable_user(username):
        print(f"User '{username}' enabled successfully")
        return 0
    else:
        print(f"Error: User '{username}' not found")
        return 1


def change_password(db: Database, username: str, new_password: str = None):
    """Change user password."""
    # Check if user exists
    user = db.get_user(username)
    if not user:
        print(f"Error: User '{username}' not found")
        return 1

    # Get new password
    if not new_password:
        new_password = getpass.getpass("Enter new password: ")
        password_confirm = getpass.getpass("Confirm new password: ")

        if new_password != password_confirm:
            print("Error: Passwords do not match")
            return 1

    if len(new_password) < 8:
        print("Error: Password must be at least 8 characters")
        return 1

    # Hash new password
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Update password
    if db.change_password(username, password_hash):
        print(f"Password changed successfully for user '{username}'")
        return 0
    else:
        print(f"Error: Failed to change password for user '{username}'")
        return 1


def reset_totp(db: Database, username: str, conference_name: str = "ChallengeCtl"):
    """Reset TOTP secret for a user."""
    # Check if user exists
    user = db.get_user(username)
    if not user:
        print(f"Error: User '{username}' not found")
        return 1

    # Generate new TOTP secret
    totp_secret = pyotp.random_base32()

    # Encrypt TOTP secret before storing
    encrypted_totp_secret = encrypt_totp_secret(totp_secret)

    # Update user (reuse password_hash from existing user)
    password_hash = user['password_hash']

    # We need to update the TOTP secret - but we don't have a method for that
    # Let's update via SQL directly
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET totp_secret = ?
            WHERE username = ?
        ''', (encrypted_totp_secret, username))
        conn.commit()

    print(f"\nTOTP secret reset successfully for user '{username}'!")
    print(f"\nNew TOTP Secret: {totp_secret}")
    print("\nSetup TOTP in your authenticator app:")
    print("1. Scan the QR code below, OR")
    print("2. Manually enter the secret above")

    # Generate QR code
    totp = pyotp.TOTP(totp_secret)
    provisioning_uri = totp.provisioning_uri(name=username, issuer_name=conference_name)

    print("\nQR Code:")
    qr = qrcode.QRCode()
    qr.add_data(provisioning_uri)
    qr.print_ascii(invert=True)

    print(f"\nProvisioning URI: {provisioning_uri}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Manage admin users for ChallengeCtl server'
    )

    parser.add_argument(
        '--db',
        default='challengectl.db',
        help='Path to database file (default: challengectl.db)'
    )

    parser.add_argument(
        '--config',
        default='server-config.yml',
        help='Path to server config file (default: server-config.yml)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create user
    create_parser = subparsers.add_parser('create', help='Create a new user')
    create_parser.add_argument('username', help='Username for the new user')
    create_parser.add_argument('--password', help='Password (will prompt if not provided)')

    # List users
    subparsers.add_parser('list', help='List all users')

    # Disable user
    disable_parser = subparsers.add_parser('disable', help='Disable a user account')
    disable_parser.add_argument('username', help='Username to disable')

    # Enable user
    enable_parser = subparsers.add_parser('enable', help='Enable a user account')
    enable_parser.add_argument('username', help='Username to enable')

    # Change password
    passwd_parser = subparsers.add_parser('change-password', help='Change user password')
    passwd_parser.add_argument('username', help='Username')
    passwd_parser.add_argument('--password', help='New password (will prompt if not provided)')

    # Reset TOTP
    totp_parser = subparsers.add_parser('reset-totp', help='Reset TOTP secret for a user')
    totp_parser.add_argument('username', help='Username')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize database
    db = Database(args.db)

    # Load config and get conference name
    config = load_config(args.config)
    conference_name = get_conference_name(config)

    # Execute command
    if args.command == 'create':
        return create_user(db, args.username, args.password, conference_name)
    elif args.command == 'list':
        return list_users(db)
    elif args.command == 'disable':
        return disable_user(db, args.username)
    elif args.command == 'enable':
        return enable_user(db, args.username)
    elif args.command == 'change-password':
        return change_password(db, args.username, args.password)
    elif args.command == 'reset-totp':
        return reset_totp(db, args.username, conference_name)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
