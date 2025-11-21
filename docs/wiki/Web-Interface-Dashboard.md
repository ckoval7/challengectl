# Dashboard

The dashboard provides an overview of system status and recent activity.

## Statistics Panel

The top section displays key metrics:

**Total Runners**: Number of registered runners (includes online and offline)

**Active Runners**: Number of runners currently online and available
- Green indicator: Healthy system
- Yellow indicator: Some runners offline
- Red indicator: No runners available

**Total Challenges**: Number of configured challenges in the system

**Enabled Challenges**: Number of challenges currently active
- Shows how many challenges are eligible for transmission

**Total Transmissions**: Cumulative count of all completed transmissions since server start

## Recent Transmissions Feed

The lower section shows real-time transmission activity:

**Columns**:
- **Challenge**: Name of the transmitted challenge
- **Runner**: Which runner executed the transmission
- **Frequency**: Transmission frequency in Hz (displayed as MHz)
- **Modulation**: Type of modulation used
- **Status**: Success or failure indicator
- **Timestamp**: When the transmission completed

**Status Indicators**:
- Green checkmark: Successful transmission
- Red X: Failed transmission (hover for error details)

**Auto-refresh**: The feed updates automatically as transmissions complete via WebSocket events.

## Conference Settings Card

The Conference Settings card on the Dashboard allows you to configure conference-specific features including daily operating hours, countdown timers, and automatic pause/resume.

For detailed information about conference settings, see the [System Controls Guide](Web-Interface-System-Controls#conference-settings).

## Related Guides

- [Runners Management](Web-Interface-Runners) - Monitor and control runners
- [Challenge Management](Web-Interface-Challenges) - Manage challenges
- [System Controls](Web-Interface-System-Controls) - Configure conference settings
- [Logs Viewer](Web-Interface-Logs) - View detailed logs
