#!/bin/bash
# Fix fhss_tx.py import to support relative imports after GRC generation
# Usage: ./fix-fhss-import.sh

set -e

FHSS_FILE="challenges/fhss_tx.py"

if [ ! -f "$FHSS_FILE" ]; then
    echo "Error: $FHSS_FILE not found"
    exit 1
fi

# Check if the file has already been fixed
if grep -q "from . import fhss_tx_hop_set" "$FHSS_FILE"; then
    echo "$FHSS_FILE already has relative import support"
    exit 0
fi

# Replace the import line with try/except logic
sed -i.bak '/^import fhss_tx_hop_set as hop_set/c\
try:\
    # Try relative import first (when imported as part of challenges package)\
    from . import fhss_tx_hop_set as hop_set\
except ImportError:\
    # Fall back to direct import (when run as __main__)\
    import fhss_tx_hop_set as hop_set  # embedded python module
' "$FHSS_FILE"

echo "✓ Fixed import in $FHSS_FILE"
echo "Backup saved as ${FHSS_FILE}.bak"
