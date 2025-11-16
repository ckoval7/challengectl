#!/bin/bash
# Reset database and show default admin credentials

echo "This will delete the existing database and create a fresh one."
echo "You will lose all existing data (users, challenges, transmissions, etc.)"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

cd "$(dirname "$0")"

# Find and remove database files
echo "Removing existing database files..."
rm -f challengectl.db server/challengectl.db *.db server/*.db 2>/dev/null

echo ""
echo "Database reset. Start the server to see default admin credentials:"
echo ""
echo "  cd server"
echo "  python server.py"
echo ""
echo "Look for the DEFAULT ADMIN USER CREATED message in the logs."
