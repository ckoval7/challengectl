# Logs Viewer

The Logs page provides real-time log streaming from the server and all connected runners.

## Log Display

**Columns**:
- **Timestamp**: When the log entry was created
- **Source**: Where the log originated (server or runner ID)
- **Level**: Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Message**: The log message content

**Color Coding**:
- **Gray**: DEBUG messages
- **White**: INFO messages
- **Yellow**: WARNING messages
- **Red**: ERROR and CRITICAL messages

## Filtering Logs

### By Source

- **All**: Show logs from server and all runners
- **Server**: Show only server logs
- **Runner ID**: Show logs from a specific runner

### By Level

- **All**: Show all log levels
- **INFO and above**: Hide DEBUG messages
- **WARNING and above**: Show only warnings and errors
- **ERROR only**: Show only errors

## Log Features

### Auto-scroll

Automatically scroll to newest entries
- Toggle on/off with the auto-scroll button
- Disable to review historical logs

### Search

Filter logs by text search
- Searches across all columns
- Case-insensitive
- Updates in real-time

### Export

Download logs for offline analysis
- Exports currently filtered logs
- CSV format
- Includes timestamp, source, level, and message

## Common Log Patterns

### Normal Operation

```
[INFO] Runner runner-1 registered successfully
[INFO] Challenge NBFM_FLAG_1 assigned to runner-1
[INFO] Challenge NBFM_FLAG_1 completed successfully
```

### Warning Signs

```
[WARNING] Runner runner-1 heartbeat timeout warning
[WARNING] No runners available for challenge assignment
```

### Errors

```
[ERROR] Challenge transmission failed: Device not found
[ERROR] Database lock timeout
[ERROR] File not found: challenges/missing.wav
```

## Troubleshooting with Logs

### Runner Issues

1. Filter by source to show only that runner's logs
2. Look for connection errors or device failures
3. Check for warnings about missing files or configuration issues

### Challenge Issues

1. Search for the challenge name
2. Look for file not found errors
3. Check for frequency or modulation errors

### System Issues

1. Filter to show ERROR level only
2. Look for database lock messages
3. Check for file permission errors

### Performance Issues

1. Look for WARNING messages about timeouts
2. Check for "slow query" or "database lock" messages
3. Monitor for repeated error patterns

## Real-Time Updates

The Logs page updates automatically via WebSocket connections:
- New log entries appear instantly
- Auto-scroll keeps you at the bottom (if enabled)
- Filtering and search work on live data

## Related Guides

- [Runners Management](Web-Interface-Runners) - Troubleshoot runner issues
- [Challenges](Web-Interface-Challenges) - Debug challenge problems
- [Dashboard](Web-Interface-Dashboard) - Monitor system health
- [Advanced Topics](Web-Interface-Advanced) - WebSocket connection status
