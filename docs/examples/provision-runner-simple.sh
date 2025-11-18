#!/bin/bash
#
# ChallengeCtl - Simple Runner Provisioning with API Key
#
# This script demonstrates provisioning a runner using a provisioning API key.
# No admin credentials or CSRF tokens required!
#
# Usage:
#   ./provision-runner-simple.sh <server_url> <provisioning_api_key> <runner_name>
#
# Example:
#   ./provision-runner-simple.sh https://localhost:8443 ck_prov_abc123... my-runner-1
#

set -e

if [ $# -ne 3 ]; then
    echo "Usage: $0 <server_url> <provisioning_api_key> <runner_name>"
    echo ""
    echo "Example:"
    echo "  $0 https://localhost:8443 ck_prov_abc123xyz my-runner-1"
    exit 1
fi

SERVER_URL="$1"
PROVISIONING_KEY="$2"
RUNNER_NAME="$3"

CONFIG_FILE="runner-config-${RUNNER_NAME}.yml"

echo "=========================================="
echo "ChallengeCtl Runner Provisioning"
echo "=========================================="
echo "Server: $SERVER_URL"
echo "Runner: $RUNNER_NAME"
echo ""

# Provision the runner
echo "[1/2] Provisioning runner..."
RESPONSE=$(curl -s -k \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $PROVISIONING_KEY" \
    -d "{\"runner_name\":\"$RUNNER_NAME\"}" \
    "$SERVER_URL/api/provisioning/provision")

# Check for errors
if echo "$RESPONSE" | grep -q '"error"'; then
    echo "Error: Provisioning failed"
    echo "$RESPONSE" | grep -o '"error":"[^"]*' | cut -d'"' -f4
    exit 1
fi

# Extract the YAML config
CONFIG_YAML=$(echo "$RESPONSE" | grep -o '"config_yaml":"' | wc -l)
if [ "$CONFIG_YAML" -eq 0 ]; then
    echo "Error: No config_yaml in response"
    exit 1
fi

# Save the config (using python to properly parse JSON and unescape YAML)
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['config_yaml'])
" > "$CONFIG_FILE"

echo "✓ Runner provisioned successfully"

# Display credentials summary
echo ""
echo "[2/2] Configuration saved to: $CONFIG_FILE"
echo ""
echo "Runner Details:"
echo "  Name: $RUNNER_NAME"
echo "  Config: $CONFIG_FILE"
echo ""
echo "Next steps:"
echo "  1. Copy $CONFIG_FILE to your runner machine"
echo "  2. Customize the 'radios.devices' section"
echo "  3. Start the runner:"
echo "     python -m challengectl.runner.runner --config $CONFIG_FILE"
echo ""
echo "  4. After first successful run:"
echo "     - Remove the 'enrollment_token' line from the config"
echo "     - Restart the runner"
echo ""
echo "=========================================="
