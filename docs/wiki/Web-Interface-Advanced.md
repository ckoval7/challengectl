# Advanced Topics

This guide covers advanced features and best practices for using the ChallengeCtl web interface.

## Real-Time Updates

The web interface uses WebSocket connections for real-time updates without page refreshes.

### What Updates in Real-Time

**Dashboard**:
- Statistics counters
- Recent transmissions feed
- Runner online/offline status

**Runners Page**:
- Runner status (online, busy, offline)
- Last heartbeat timestamps
- Current task assignments

**Challenges Page**:
- Challenge state changes (queued, waiting, assigned)
- Last run timestamps
- Enable/disable status

**Logs Page**:
- New log entries from server and runners
- Continuous log streaming

### WebSocket Connection Status

**Connected**: Green indicator in the top-right corner
- Updates flow normally
- No action needed

**Disconnected**: Red indicator in the top-right corner
- Updates stop
- Page data becomes stale
- Browser automatically attempts to reconnect

**Reconnecting**: Yellow indicator
- Connection lost, attempting to restore
- Wait a few seconds for automatic reconnection

### If WebSocket Fails

1. **Check your network connection**: Ensure you're connected to the network
2. **Refresh the page**: Force reconnection by reloading
3. **Check server logs**: Look for WebSocket errors
4. **Verify reverse proxy**: If using nginx, ensure WebSocket proxying is configured
5. **Manual refresh**: You can still use the interface, but you'll need to manually refresh pages

## Tips and Best Practices

### Event Management

**Before the event**:
- Test all challenges with "Trigger Now"
- Verify all runners are online and enabled
- Set up log filtering to reduce noise
- Create backup admin accounts

**During the event**:
- Monitor the dashboard for anomalies
- Watch logs for errors
- Use pause (not stop) for short breaks
- Disable problematic runners rather than kicking them
- Use manual trigger for demonstrations

**After the event**:
- Export logs for analysis
- Review transmission history
- Disable all challenges or stop the server
- Back up the database

### Troubleshooting Through the UI

**Runner won't go online**:
1. Check the Runners page for the runner
2. If listed but offline, check last heartbeat time
3. Check Logs page for connection errors from that runner ID
4. Consider kicking and letting it re-register

**Challenge won't transmit**:
1. Check **Manage Challenges > Live Status** tab for the challenge state
2. Verify at least one runner is online and enabled
3. Check runner frequency limits include the challenge frequency
4. Look for errors in Logs page
5. Try manual trigger from Live Status tab to test

**System slow or unresponsive**:
1. Check number of active runners (too many?)
2. Review recent transmissions for high failure rate
3. Check Logs for database lock errors
4. Consider pausing system temporarily
5. Check server resource usage externally

### Security Best Practices

1. **Use HTTPS**: Always run behind nginx with TLS in production
2. **Strong passwords**: Enforce strong password requirements
3. **Limit access**: Use firewall rules to restrict web UI access
4. **Regular backups**: Back up the database including user accounts
5. **Monitor logs**: Watch for suspicious login attempts
6. **Logout when done**: Especially on shared computers
7. **Rotate passwords**: Change admin passwords periodically

## Performance Optimization

### Reducing Database Load

- Disable auto-refresh on pages you're not actively monitoring
- Use log filtering to reduce log volume
- Archive old transmission history periodically

### Managing WebSocket Connections

- Close unused browser tabs to reduce WebSocket load
- Use a single admin session when possible
- WebSocket reconnects automatically after brief disconnections

### Large-Scale Deployments

- Consider read-only accounts for observers
- Use log export instead of live streaming for analysis
- Monitor server resource usage during events
- Use pagination for large challenge lists

## Browser Compatibility

The web interface is tested and supported on:

- **Chrome/Chromium**: Version 90+
- **Firefox**: Version 88+
- **Safari**: Version 14+
- **Edge**: Version 90+

**Features requiring modern browsers**:
- WebSocket connections (all real-time updates)
- ES6 JavaScript features
- CSS Grid and Flexbox layouts

**Recommended**:
- Use the latest version of Chrome or Firefox for best performance
- Enable JavaScript (required for all functionality)
- Allow WebSocket connections through firewalls

## API Access

For programmatic access to ChallengeCtl, see:
- [API Reference](API-Reference) - Complete API documentation
- [Challenge Import API](Web-Interface-Challenges#api-automation) - YAML import automation

## Keyboard Shortcuts

Currently, the web interface uses standard browser shortcuts:

- **Ctrl+R** / **Cmd+R**: Refresh current page
- **Ctrl+F** / **Cmd+F**: Search (in logs or tables)
- **Ctrl+W** / **Cmd+W**: Close tab

## Customization

### Conference Branding

Conference name and timing are configured in `server-config.yml`:

```yaml
conference:
  name: "Your Conference Name"
  start: "2024-04-05 09:00:00 -5"
  stop: "2024-04-07 17:00:00 -5"
```

These settings appear in:
- Header countdown timer
- Public dashboard
- Conference settings card

### Page Titles

Page titles update based on:
- Current page (Dashboard, Runners, etc.)
- Conference name (from config)
- Notification counts (future feature)

## Mobile Access

The web interface is responsive and works on mobile devices:

**Best Practices for Mobile**:
- Use landscape orientation for tables
- Dashboard works well in portrait mode
- Log viewer is easier to read in landscape
- Touch-friendly buttons and controls

**Limitations on Mobile**:
- Tables may require horizontal scrolling
- Log export may not work on all mobile browsers
- WebSocket connections may be interrupted during screen sleep

## Next Steps

- [Configuration Reference](Configuration-Reference) - Advanced server configuration
- [API Reference](API-Reference) - Programmatic access
- [Architecture Overview](Architecture) - Understanding system design
- [Troubleshooting Guide](Troubleshooting) - Common issues and solutions
