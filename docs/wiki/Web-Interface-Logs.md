# Logs Viewer

The Logs page provides real-time log streaming from the server and all connected runners. This centralized view allows you to monitor system activity, diagnose issues, and track the status of challenges and runner operations as they happen.

!["Screenshot of log streaming display"](/docs/images/logs.png "Log Streaming")

## Log Display

Each log entry displays four key pieces of information to help you understand what is happening in your system. The timestamp shows when the log entry was created, allowing you to establish a timeline of events. The source indicates where the log originated, whether from the server itself or from a specific runner identified by its ID. The level represents the severity of the message, ranging from DEBUG for detailed diagnostic information up through INFO, WARNING, ERROR, and CRITICAL for the most severe issues. Finally, the message contains the actual log content describing what occurred.

To make it easier to spot issues at a glance, log entries are color-coded by severity. DEBUG messages appear in gray, indicating routine diagnostic information. INFO messages display in white for standard operational notifications. WARNING messages are highlighted in yellow to draw attention to potential issues. ERROR and CRITICAL messages appear in red to immediately signal problems that require attention.

## Filtering Logs

### By Source

The source filter allows you to focus on logs from specific parts of your system. You can view logs from all sources simultaneously to see the complete picture of system activity. Filtering to show only server logs helps when troubleshooting server-side issues such as database operations or API requests. Narrowing down to logs from a specific runner by selecting its ID proves particularly useful when diagnosing problems with individual runner devices or tracking the progress of challenges assigned to particular runners.

### By Level

Log level filtering helps you focus on the information that matters most for your current task. When set to show all levels, you see every log entry from verbose DEBUG messages through CRITICAL errors. The "INFO and above" filter hides DEBUG messages, reducing noise while still showing all operational logs and warnings. "WARNING and above" further narrows the view to show only potential problems and errors. The "ERROR only" setting displays just the errors and critical issues, making it easy to identify what needs immediate attention.

## Log Features

### Auto-scroll

The auto-scroll feature keeps your view focused on the most recent log entries as they arrive in real-time. When enabled, the log display automatically scrolls to show new entries as they appear, ensuring you never miss the latest events. You can toggle this feature on or off using the auto-scroll button. Disabling auto-scroll proves useful when you need to review historical log entries or examine a specific sequence of events without the view jumping to new messages.

### Search

The search functionality allows you to quickly find specific log entries by filtering based on text content. The search works across all columns in the log display, including the message text and source identifier. Searches are case-insensitive, making it easy to find what you're looking for without worrying about exact capitalization. As you type, the results update in real-time, instantly showing only the entries that match your search criteria.

### Export

The export feature enables you to download logs for offline analysis, archival, or sharing with team members. When you export logs, the system captures the currently filtered set of entries, respecting any source, level, or search filters you have active. You can choose between plain text format for easy readability or CSV format for importing into spreadsheet applications and analysis tools. The exported file includes all four log fields providing complete information for later review.

## Common Log Patterns

### Normal Operation

During normal operation, you will typically see patterns indicating healthy system function. A runner registration message such as "[INFO] Runner runner-1 registered successfully" confirms that a runner has connected to the server. Challenge assignment messages like "[INFO] Challenge NBFM_FLAG_1 assigned to runner-1" show the normal distribution of work. Completion messages such as "[INFO] Challenge NBFM_FLAG_1 completed successfully" verify that transmissions are executing correctly.

### Warning Signs

Certain warning patterns indicate potential issues that may require attention. A heartbeat timeout warning such as "[WARNING] Runner runner-1 heartbeat timeout warning" suggests that a runner may be experiencing connectivity problems. Availability warnings like "[WARNING] No runners available for challenge assignment" indicate that the system cannot assign work due to lack of available resources.

### Errors

Error messages signal problems that require investigation and resolution. Device errors such as "[ERROR] Challenge transmission failed: Device not found" indicate hardware or configuration problems with SDR devices. Database errors like "[ERROR] Database lock timeout" suggest performance or concurrency issues. File errors such as "[ERROR] File not found: challenges/missing.wav" point to missing resources or configuration problems.

## Troubleshooting with Logs

### Runner Issues

When troubleshooting problems with a specific runner, start by using the source filter to display only that runner's logs. This focused view makes it easier to spot connection errors, device failures, or communication problems specific to that unit. Look for warnings about missing files or configuration issues that might prevent the runner from operating correctly. Pay attention to the pattern of messages to determine whether the problem is intermittent or persistent, as this information guides your troubleshooting approach.

### Challenge Issues

If a particular challenge is not transmitting correctly, use the search feature to find all log entries mentioning that challenge's name. Look for "file not found" errors that might indicate missing audio files or configuration problems preventing execution. Check for frequency validation errors or modulation-specific issues that could prevent successful transmission. The sequence of log entries will often reveal whether the challenge is being assigned to runners but failing during transmission, or if it is not being assigned at all, helping you narrow down the root cause.

### System Issues

When investigating broader system problems, filter the logs to show only ERROR level messages to quickly identify critical issues requiring immediate attention. Look for database lock messages that might indicate performance bottlenecks or concurrency problems affecting overall system operation. Check for file permission errors that could prevent the server from accessing necessary resources. If you see repeated patterns of errors, this often indicates a configuration issue rather than a transient problem, suggesting that system-level changes may be needed.

### Performance Issues

Performance problems often reveal themselves through WARNING level messages before escalating to errors. Look for timeout warnings that suggest operations are taking longer than expected. Check for "slow query" or "database lock" messages that indicate database performance issues affecting responsiveness. Monitor for repeated error patterns that might indicate a resource is being exhausted or a bottleneck is being hit regularly. The timing of these messages can help identify peak load periods or specific operations that need optimization.

## Real-Time Updates

The Logs page maintains an active WebSocket connection to provide immediate updates as events occur throughout the system. New log entries appear instantly without requiring a page refresh, giving you a live view of system activity. When auto-scroll is enabled, the display automatically stays positioned at the most recent entries. All filtering and search operations work seamlessly on this live data stream, allowing you to focus on relevant information even as new logs continue to arrive.

## Related Guides

For troubleshooting runner issues identified in logs, see the Runners Management guide. To debug challenge problems revealed through log analysis, consult the Challenges guide. For monitoring overall system health alongside log data, refer to the Dashboard guide. For understanding WebSocket connection status and its impact on real-time updates, see the Advanced Topics guide.
