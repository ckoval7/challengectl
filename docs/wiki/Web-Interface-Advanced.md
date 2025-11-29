# Advanced Topics

This guide covers advanced features and best practices for using the ChallengeCtl web interface effectively.

## Real-Time Updates

The web interface uses WebSocket connections for real-time updates, eliminating the need for manual page refreshes to see current system state.

### What Updates in Real-Time

The Dashboard displays several elements that update automatically. Statistics counters refresh as values change, providing current metrics at all times. The recent transmissions feed updates as transmissions complete, showing activity as it happens. Runner online and offline status changes reflect immediately, indicating connectivity changes.

The Runners Page updates comprehensively in real-time. Runner status transitions between online, busy, and offline states appear immediately. Last heartbeat timestamps refresh continuously, showing the most recent contact time. Current task assignments display as soon as runners claim work, providing visibility into active operations.

The Challenges Page reflects challenge state in real-time. Challenge state changes between queued, waiting, and assigned appear immediately as the system processes tasks. Last run timestamps update when transmissions complete. Enable and disable status changes show immediately when administrators modify challenge configuration.

The Logs Page provides continuous real-time streaming. New log entries from server and runners appear as events occur. The interface maintains continuous log streaming without interruption, ensuring no events are missed.

### WebSocket Connection Status

The interface displays connection status using a visual indicator in the top-right corner. A green indicator shows the connected state, confirming that updates flow normally and no action is needed. A red indicator shows the disconnected state, meaning updates have stopped and page data becomes stale. The browser automatically attempts to reconnect when disconnection occurs. A yellow indicator shows the reconnecting state, indicating connection was lost and the system is attempting to restore it. Wait a few seconds for automatic reconnection when you see this indicator.

### If WebSocket Fails

If WebSocket connectivity fails, several troubleshooting steps can help restore functionality. Check your network connection to ensure you are connected to the network and can reach the server. Refresh the page to force reconnection, which often resolves transient issues. Check server logs for WebSocket errors that might indicate server-side problems. Verify reverse proxy configuration if using nginx, ensuring WebSocket proxying is properly configured. If automatic reconnection fails, you can still use the interface but will need to manually refresh pages to see updated information.

## Tips and Best Practices

### Event Management

Before an event begins, test all challenges using the "Trigger Now" function to verify correct operation. Verify all runners are online and enabled to ensure capacity for challenge distribution. Set up log filtering to reduce noise and focus on important events. Create backup admin accounts to ensure access even if primary accounts experience issues.

During the event, monitor the dashboard for anomalies that might indicate problems. Watch logs for errors that require investigation or intervention. Use pause rather than stop for short breaks, as this maintains all system state. Disable problematic runners rather than kicking them to preserve their configuration while troubleshooting. Use manual trigger for demonstrations when showing specific challenges on demand.

After the event, export logs for analysis to understand system performance and any issues encountered. Review transmission history to evaluate challenge distribution and execution. Disable all challenges or stop the server to prevent continued transmission. Back up the database to preserve event data for later reference or analysis.

### Troubleshooting Through the UI

When a runner refuses to go online, start by checking the Runners page for the runner entry. If the runner is listed but offline, check the last heartbeat time to determine how long it has been disconnected. Check the Logs page for connection errors from that runner ID that might indicate the cause. Consider kicking the runner to force re-registration, which often resolves authentication or connection state issues.

When a challenge refuses to transmit, check the Manage Challenges Live Status tab for the challenge state to understand its current status. Verify at least one runner is online and enabled, as challenges cannot transmit without available runners. Check runner frequency limits to ensure they include the challenge frequency, as frequency mismatch prevents assignment. Look for errors in the Logs page that indicate configuration or execution problems. Try manual trigger from the Live Status tab to test whether the challenge can execute on demand.

When the system becomes slow or unresponsive, check the number of active runners to determine if too many are connected. Review recent transmissions for high failure rates that might indicate systemic problems. Check logs for database lock errors that suggest performance or concurrency issues. Consider pausing the system temporarily to reduce load while investigating. Check server resource usage externally using system monitoring tools to identify resource constraints.

### Security Best Practices

Always use HTTPS in production environments by running the web interface behind nginx with TLS configured. Enforce strong password requirements for all user accounts to prevent unauthorized access through weak credentials. Limit access using firewall rules to restrict web UI access to authorized networks or IP addresses only. Perform regular backups of the database including user accounts, system state, and challenge configuration. Monitor logs continuously for suspicious login attempts or unusual activity patterns that might indicate security issues. Always logout when done, especially when using shared computers to prevent unauthorized access. Rotate passwords regularly by changing admin passwords periodically to maintain security even if credentials become compromised.

## Performance Optimization

### Reducing Database Load

Disable auto-refresh on pages you are not actively monitoring to reduce query frequency. Use log filtering to reduce log volume and improve display performance. Archive old transmission history periodically to keep the database size manageable and queries responsive.

### Managing WebSocket Connections

Close unused browser tabs to reduce WebSocket load on the server. Use a single admin session when possible to minimize connection overhead. The WebSocket automatically reconnects after brief disconnections, so temporary network issues resolve themselves.

### Large-Scale Deployments

For deployments with many observers, consider read-only accounts that can view but not modify system state. Use log export instead of live streaming for analysis when real-time monitoring is not required. Monitor server resource usage during events to identify bottlenecks before they impact operations. Use pagination for large challenge lists to improve interface responsiveness.

## Browser Compatibility

The web interface is tested and supported on modern browsers. Chrome and Chromium version 90 and above provide full support. Firefox version 88 and above is fully supported. Safari version 14 and above works correctly with all features. Edge version 90 and above provides complete functionality.

Several features require modern browsers for correct operation. WebSocket connections, which enable all real-time updates, require modern browser support. ES6 JavaScript features are used throughout the interface. CSS Grid and Flexbox layouts provide the responsive interface design.

For best results, use the latest version of Chrome or Firefox for optimal performance and compatibility. Enable JavaScript, as it is required for all functionality. Allow WebSocket connections through firewalls to enable real-time updates.

## API Access

For programmatic access to ChallengeCtl beyond the web interface, consult the API Reference for complete API documentation. The Challenge Import API section of the Challenges guide covers YAML import automation for batch challenge management.

## Keyboard Shortcuts

The web interface currently uses standard browser shortcuts for common operations. Control-R or Command-R refreshes the current page. Control-F or Command-F opens search in logs or tables. Control-W or Command-W closes the current tab.

## Customization

### Conference Branding

Conference name and timing configuration resides in server-config.yml. The conference section defines the name, start time, and stop time. These settings appear in multiple locations throughout the interface, including the header countdown timer, public dashboard, and conference settings card.

### Page Titles

Page titles update dynamically based on several factors. The current page determines the base title, such as Dashboard or Runners. The conference name from configuration appears in the title. Notification counts may appear in the title in future versions to alert administrators of important events.

## Mobile Access

The web interface is responsive and works on mobile devices with appropriate design considerations.

For best practices on mobile devices, use landscape orientation for viewing tables as they are optimized for wider displays. Dashboard works well in portrait mode, providing quick status overview. The log viewer is easier to read in landscape orientation. Touch-friendly buttons and controls ensure easy operation on touchscreen devices.

Mobile devices have some limitations to consider. Tables may require horizontal scrolling on narrow screens. Log export may not work on all mobile browsers due to platform limitations. WebSocket connections may be interrupted during screen sleep, requiring page refresh when the device wakes.

## Next Steps

For advanced server configuration beyond the web interface, consult the Configuration Reference. For programmatic access through the API, see the API Reference. To understand system design and how the UI interacts with the backend, review the Architecture Overview. For common issues and their solutions, refer to the Troubleshooting Guide.
