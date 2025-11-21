# Web Interface Guide

This guide covers the ChallengeCtl web interface, explaining how to monitor system status, manage challenges and runners, and control system operation through the browser-based dashboard.

## Overview

The ChallengeCtl web interface provides a comprehensive view of your RF challenge distribution system. It allows administrators to monitor system health, manage runners and challenges, view real-time logs, and control system operation without needing to edit configuration files or restart services.

### Key Features

- **Real-time monitoring**: Live updates via WebSocket connections
- **Challenge management**: Enable, disable, and manually trigger challenges
- **Challenge configuration**: Create, import, edit, and delete challenges via Web UI
- **Runner control**: Monitor runner status and manage connections
- **Log streaming**: Real-time logs from server and all runners
- **User administration**: Manage admin accounts and credentials
- **System controls**: Pause and resume operations
- **Conference countdown**: Live countdown timers with daily hour cycling
- **Auto-pause scheduling**: Automatically pause/resume based on daily hours

## Documentation Sections

This guide is organized into the following sections for easier navigation:

### Getting Started

**[Web Interface Overview](Web-Interface-Overview)**
- Overview of the web interface
- Accessing and logging in
- Session management
- User menu options
- Navigation
- Security best practices

### Core Features

**[Dashboard](Web-Interface-Dashboard)**
- Statistics panel
- Recent transmissions feed
- Conference settings card

**[Runners Management](Web-Interface-Runners)**
- Runner list and status
- Runner actions (enable, disable, kick)
- When to disable vs kick
- Real-time updates
- Troubleshooting runners

**[Challenge Management](Web-Interface-Challenges)**
- Live Status tab (monitoring and control)
- Create Challenge tab (form-based creation)
- Import from YAML tab (batch import)
- Manage Challenges tab (edit and delete)
- API automation
- Best practices
- Typical workflow

**[User Management](Web-Interface-Users)**
- User list and operations
- Adding users
- User account types
- Managing permissions
- Password and TOTP management
- Security features
- Common workflows

**[System Controls](Web-Interface-System-Controls)**
- Pause vs disable operations
- Reload configuration
- Conference settings
  - Conference name and countdown
  - Daily operating hours
  - Auto-pause daily
  - Configuration workflow
  - Best practices

**[Logs Viewer](Web-Interface-Logs)**
- Log display and color coding
- Filtering by source and level
- Auto-scroll, search, and export
- Common log patterns
- Troubleshooting with logs

### Advanced Topics

**[Advanced Topics](Web-Interface-Advanced)**
- Real-time updates (WebSocket)
- Tips and best practices
- Troubleshooting through the UI
- Performance optimization
- Browser compatibility
- API access
- Mobile access

## Quick Navigation

### Common Tasks

- **Monitor system health**: [Dashboard](Web-Interface-Dashboard)
- **Add a new challenge**: [Create Challenge](Web-Interface-Challenges#create-challenge-tab)
- **Import multiple challenges**: [Import from YAML](Web-Interface-Challenges#import-from-yaml-tab)
- **Enable/disable a challenge**: [Live Status](Web-Interface-Challenges#live-status-tab)
- **Test a challenge**: [Trigger Now](Web-Interface-Challenges#actions-available)
- **Manage runners**: [Runners Management](Web-Interface-Runners)
- **Add a new admin user**: [Add User](Web-Interface-Users#add-user)
- **Pause the system**: [System Controls](Web-Interface-System-Controls#pause-system)
- **Set up conference hours**: [Conference Settings](Web-Interface-System-Controls#conference-settings)
- **View logs**: [Logs Viewer](Web-Interface-Logs)
- **Troubleshoot issues**: [Advanced Topics - Troubleshooting](Web-Interface-Advanced#troubleshooting-through-the-ui)

## Getting Help

If you need additional information:

- [Challenge Management Guide](Challenge-Management) - Detailed challenge configuration
- [API Reference](API-Reference) - Programmatic access
- [Architecture Overview](Architecture) - Understanding how the UI interacts with the backend
- [Troubleshooting Guide](Troubleshooting) - Common issues
- [Configuration Reference](Configuration-Reference) - Advanced setup options

## Next Steps

1. **First time using the interface?** Start with [Web Interface Overview](Web-Interface-Overview)
2. **Setting up for an event?** Review [Challenge Management](Web-Interface-Challenges) and [System Controls](Web-Interface-System-Controls)
3. **Need to troubleshoot?** Check [Logs Viewer](Web-Interface-Logs) and [Advanced Topics](Web-Interface-Advanced)
4. **Managing users?** See [User Management](Web-Interface-Users)
