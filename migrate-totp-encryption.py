#!/usr/bin/env python3
"""
Database migration script to encrypt existing TOTP secrets.
This script encrypts all plaintext TOTP secrets in the database.
"""

import argparse
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from database import Database
from crypto import encrypt_totp_secret, decrypt_totp_secret


def migrate_totp_secrets(db: Database, dry_run: bool = False):
    """
    Migrate all unencrypted TOTP secrets to encrypted format.

    Args:
        db: Database instance
        dry_run: If True, only show what would be done without actually doing it
    """
    print("Starting TOTP secret encryption migration...")
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE'}")
    print()

    # Get all users
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, totp_secret FROM users WHERE totp_secret IS NOT NULL')
        users = cursor.fetchall()

    if not users:
        print("No users with TOTP secrets found.")
        return 0

    print(f"Found {len(users)} user(s) with TOTP secrets.")
    print()

    migrated_count = 0
    already_encrypted_count = 0
    error_count = 0

    for row in users:
        username = row['username']
        encrypted_secret = row['totp_secret']

        # Try to decrypt the secret
        decrypted_secret = decrypt_totp_secret(encrypted_secret)

        if decrypted_secret is None:
            # Decryption failed - this is a legacy unencrypted secret
            print(f"User '{username}': Needs migration (unencrypted)")

            if not dry_run:
                try:
                    # The secret is already plaintext, so we just need to encrypt it
                    newly_encrypted = encrypt_totp_secret(encrypted_secret)

                    # Update the database
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE users
                            SET totp_secret = ?
                            WHERE username = ?
                        ''', (newly_encrypted, username))
                        conn.commit()

                    print(f"  → Migrated successfully")
                    migrated_count += 1
                except Exception as e:
                    print(f"  → Error: {e}")
                    error_count += 1
            else:
                print(f"  → Would be migrated (dry run)")
                migrated_count += 1
        else:
            # Decryption succeeded - secret is already encrypted
            print(f"User '{username}': Already encrypted")
            already_encrypted_count += 1

    print()
    print("Migration summary:")
    print(f"  Migrated: {migrated_count}")
    print(f"  Already encrypted: {already_encrypted_count}")
    print(f"  Errors: {error_count}")
    print()

    if dry_run and migrated_count > 0:
        print("This was a dry run. Run without --dry-run to actually migrate the secrets.")

    return 0 if error_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description='Migrate TOTP secrets to encrypted format'
    )

    parser.add_argument(
        '--db',
        default='challengectl.db',
        help='Path to database file (default: challengectl.db)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )

    args = parser.parse_args()

    # Initialize database
    db = Database(args.db)

    # Run migration
    return migrate_totp_secrets(db, dry_run=args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
