#!/bin/bash
#
# ChallengeCtl - Automated Runner Enrollment via API
#
# This script demonstrates how to programmatically enroll runners using curl.
# It performs the full workflow: login, generate credentials, and enroll.
#
# Usage:
#   ./enroll-runner-api.sh <server_url> <admin_user> <admin_password> <runner_name> <runner_id>
#
# Example:
#   ./enroll-runner-api.sh https://localhost:8443 admin mypassword sdr-station-1 sdr-station-1
#

set -e  # Exit on error

# Check arguments
if [ $# -ne 5 ]; then
    echo "Usage: $0 <server_url> <admin_user> <admin_password> <runner_name> <runner_id>"
    echo ""
    echo "Example:"
    echo "  $0 https://localhost:8443 admin mypassword sdr-station-1 sdr-station-1"
    exit 1
fi

SERVER_URL="$1"
ADMIN_USER="$2"
ADMIN_PASS="$3"
RUNNER_NAME="$4"
RUNNER_ID="$5"

# Temporary files for cookies and headers
COOKIE_FILE=$(mktemp)
HEADER_FILE=$(mktemp)

# Cleanup on exit
trap "rm -f $COOKIE_FILE $HEADER_FILE" EXIT

echo "=========================================="
echo "ChallengeCtl Runner Enrollment via API"
echo "=========================================="
echo "Server: $SERVER_URL"
echo "Runner Name: $RUNNER_NAME"
echo "Runner ID: $RUNNER_ID"
echo ""

#
# Step 1: Login and get session token
#
echo "[1/4] Logging in as $ADMIN_USER..."
LOGIN_RESPONSE=$(curl -s -k \
    -c "$COOKIE_FILE" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
    "$SERVER_URL/api/auth/login")

# Check if login succeeded
if echo "$LOGIN_RESPONSE" | grep -q '"totp_required":true'; then
    echo "Error: TOTP two-factor authentication is required."
    echo "This script does not support TOTP. Please use the Web UI or disable TOTP."
    exit 1
fi

if ! echo "$LOGIN_RESPONSE" | grep -q '"status":"success"'; then
    echo "Error: Login failed"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo "✓ Login successful"

#
# Step 2: Get CSRF token from cookies
#
CSRF_TOKEN=$(grep csrf_token "$COOKIE_FILE" | awk '{print $7}')
if [ -z "$CSRF_TOKEN" ]; then
    echo "Error: Could not extract CSRF token from cookies"
    exit 1
fi

echo "✓ CSRF token obtained"

#
# Step 3: Generate enrollment token and API key
#
echo ""
echo "[2/4] Generating enrollment credentials..."
ENROLL_RESPONSE=$(curl -s -k \
    -b "$COOKIE_FILE" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    -d "{\"runner_name\":\"$RUNNER_NAME\",\"expires_hours\":24}" \
    "$SERVER_URL/api/enrollment/token")

# Extract credentials
ENROLLMENT_TOKEN=$(echo "$ENROLL_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
API_KEY=$(echo "$ENROLL_RESPONSE" | grep -o '"api_key":"[^"]*' | cut -d'"' -f4)

if [ -z "$ENROLLMENT_TOKEN" ] || [ -z "$API_KEY" ]; then
    echo "Error: Failed to generate enrollment credentials"
    echo "Response: $ENROLL_RESPONSE"
    exit 1
fi

echo "✓ Enrollment credentials generated"
echo ""
echo "  Enrollment Token: $ENROLLMENT_TOKEN"
echo "  API Key: $API_KEY"
echo ""

#
# Step 4: Enroll the runner (simulating runner enrollment)
#
echo "[3/4] Enrolling runner with server..."

# Get host information (simulating what the runner does)
HOSTNAME=$(hostname)
MAC_ADDRESS=$(ip link show | awk '/link\/ether/ {print $2; exit}')
MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "fallback-$(hostname)-$(uname -m)")

# Sample device configuration
DEVICES='[{
    "device_id": 0,
    "model": "hackrf",
    "name": "0",
    "frequency_limits": ["144000000-148000000", "420000000-450000000"]
}]'

ENROLL_RUNNER_RESPONSE=$(curl -s -k \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{
        \"enrollment_token\":\"$ENROLLMENT_TOKEN\",
        \"api_key\":\"$API_KEY\",
        \"runner_id\":\"$RUNNER_ID\",
        \"hostname\":\"$HOSTNAME\",
        \"mac_address\":\"$MAC_ADDRESS\",
        \"machine_id\":\"$MACHINE_ID\",
        \"devices\":$DEVICES
    }" \
    "$SERVER_URL/api/enrollment/enroll")

if ! echo "$ENROLL_RUNNER_RESPONSE" | grep -q '"success":true'; then
    echo "Error: Runner enrollment failed"
    echo "Response: $ENROLL_RUNNER_RESPONSE"
    exit 1
fi

echo "✓ Runner enrolled successfully"

#
# Step 5: Generate runner configuration file
#
echo ""
echo "[4/4] Generating runner-config.yml..."

CONFIG_FILE="runner-config-${RUNNER_ID}.yml"

cat > "$CONFIG_FILE" <<EOF
---
# ChallengeCtl Runner Configuration
# Generated for: $RUNNER_NAME

runner:
  # Runner identification
  runner_id: "$RUNNER_ID"

  # Server connection
  server_url: "$SERVER_URL"

  # Enrollment credentials
  # Note: enrollment_token can be left in config, it will be ignored once enrolled
  enrollment_token: "$ENROLLMENT_TOKEN"
  api_key: "$API_KEY"

  # TLS/SSL Configuration
  ca_cert: ""
  verify_ssl: true

  # Intervals
  heartbeat_interval: 30
  poll_interval: 10

  # Cache
  cache_dir: "cache"

  # Spectrum paint before challenges
  spectrum_paint_before_challenge: true

# Radio/SDR Device Configuration
radios:
  # Model defaults
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: bladerf
    rf_gain: 43
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: usrp
    rf_gain: 20
    bias_t: false
    rf_samplerate: 2000000
    ppm: 0

  # Individual devices
  devices:
  - name: 0
    model: hackrf
    rf_gain: 14
    if_gain: 32
    frequency_limits:
      - "144000000-148000000"  # 2m ham band
      - "420000000-450000000"  # 70cm ham band
EOF

echo "✓ Configuration file created: $CONFIG_FILE"

#
# Summary
#
echo ""
echo "=========================================="
echo "Enrollment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Copy $CONFIG_FILE to your runner machine"
echo "  2. Customize the 'radios.devices' section for your SDRs"
echo "  3. Start the runner:"
echo "     python -m challengectl.runner.runner --config $CONFIG_FILE"
echo ""
echo "Note: The enrollment_token can be left in the config file."
echo "      It will be ignored after the first successful enrollment."
echo ""
echo "Configuration file: $CONFIG_FILE"
echo "=========================================="
