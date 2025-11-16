#!/usr/bin/env python3
"""
Generate cryptographically secure API keys for ChallengeCtl

Usage:
    python3 generate-api-key.py [--length LENGTH] [--count COUNT]

Examples:
    python3 generate-api-key.py                    # Generate one 32-character key
    python3 generate-api-key.py --length 64        # Generate one 64-character key
    python3 generate-api-key.py --count 5          # Generate 5 keys
    python3 generate-api-key.py --length 48 --count 3  # Generate 3 48-character keys
"""

import argparse
import secrets
import string


def generate_api_key(length=32):
    """Generate a cryptographically secure random API key.

    Args:
        length: Length of the API key (default: 32)

    Returns:
        A random string suitable for use as an API key
    """
    # Use alphanumeric characters plus hyphen and underscore for readability
    alphabet = string.ascii_letters + string.digits + '-_'

    # Generate random key using secrets module (cryptographically strong)
    api_key = ''.join(secrets.choice(alphabet) for _ in range(length))

    return api_key


def main():
    parser = argparse.ArgumentParser(
        description='Generate cryptographically secure API keys for ChallengeCtl',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate one 32-character key:
    python3 generate-api-key.py

  Generate one 64-character key:
    python3 generate-api-key.py --length 64

  Generate 5 keys for multiple runners:
    python3 generate-api-key.py --count 5

  Generate 3 48-character keys:
    python3 generate-api-key.py --length 48 --count 3
        """
    )

    parser.add_argument(
        '-l', '--length',
        type=int,
        default=32,
        help='Length of each API key (default: 32)'
    )

    parser.add_argument(
        '-c', '--count',
        type=int,
        default=1,
        help='Number of API keys to generate (default: 1)'
    )

    args = parser.parse_args()

    # Validate inputs
    if args.length < 16:
        print("Error: API key length must be at least 16 characters for security")
        return 1

    if args.count < 1:
        print("Error: Count must be at least 1")
        return 1

    # Generate and display API keys
    if args.count == 1:
        print(generate_api_key(args.length))
    else:
        print(f"Generated {args.count} API keys (length: {args.length}):")
        print()
        for i in range(args.count):
            print(f"Key {i+1}: {generate_api_key(args.length)}")

    return 0


if __name__ == '__main__':
    exit(main())
