# Web Interface Guide

This guide covers the ChallengeCtl web interface, explaining how to monitor system status, manage challenges and runners, and control system operation through the browser-based dashboard.

## Overview

The ChallengeCtl web interface provides a comprehensive view of your RF challenge distribution system. It allows administrators to monitor system health, manage runners and challenges, view real-time logs, and control system operation without needing to edit configuration files or restart services.

### Key Features

The web interface delivers real-time monitoring through live updates via WebSocket connections, ensuring administrators always have current information. Challenge management functionality enables you to enable, disable, and manually trigger challenges as needed. The interface supports complete challenge configuration, allowing you to create, import, edit, and delete challenges directly through the web UI. Runner control capabilities let you monitor runner status and manage their connections effectively. Log streaming provides real-time access to logs from both the server and all connected runners. User administration features allow comprehensive management of admin accounts and credentials. System controls enable pausing and resuming operations system-wide. The conference countdown feature provides live countdown timers with support for daily hour cycling. Finally, auto-pause scheduling automatically manages system pause and resume based on configured daily operating hours.

## Documentation Sections

This guide is organized to match the web interface navigation structure, making it easy to find documentation for each section of the UI.

### Getting Started

The Web Interface Overview section covers the fundamentals of the web interface, including how to access and log in, session management, user menu options, navigation, and security best practices. This section serves as your starting point for understanding the interface.

### Main Navigation Pages

**Dashboard** - The statistics panel, recent transmissions feed, and conference settings card. This is your primary monitoring interface for overall system health.

**Agents** - Unified agent management with three tabs:
- **Runners Tab**: Runner (transmitter) agent list and status, enable/disable/kick operations, device capabilities, and real-time updates
- **Listeners Tab**: Listener (recorder) agent list and status, WebSocket connection monitoring, recording statistics, and device configuration
- **Provisioning Tab**: Enrollment token generation, API key management, agent type selection, and secure onboarding workflows

**Challenges** - Complete challenge lifecycle management with four tabs:
- **Live Status Tab**: Real-time monitoring and control, enable/disable toggles, manual trigger functionality, and inline recording galleries
- **Create Challenge Tab**: Form-based challenge creation with validation and preview
- **Import from YAML Tab**: Batch import operations with conflict resolution
- **Manage Challenges Tab**: Edit and delete existing challenges

**Recordings** - Dedicated recording history viewer (accessible from challenges), waterfall image galleries, recording metadata, filtering and search capabilities, and per-challenge recording views.

**Logs** - Real-time log streaming with color coding, filtering by source (server/runner) and level, auto-scroll and search capabilities, and export functionality.

**Users** - Admin account management including user list, add/edit/delete operations, permission assignment, password management, and TOTP two-factor authentication setup.

**Webhooks** - Discord webhook integration for real-time notifications, event subscriptions, delivery statistics, and testing functionality.

**System Controls** - Global system controls accessible from the header:
- **Pause/Resume Button**: System-wide pause control with auto-pause scheduling support
- **Conference Settings**: Conference name, countdown timers, daily operating hours configuration

**Public Dashboard** - Read-only public-facing view for spectators and participants.

### Advanced Topics

The Advanced Topics section explores real-time updates via WebSocket, tips and best practices for effective interface usage, troubleshooting techniques through the UI, performance optimization strategies, browser compatibility information, API access methods, and mobile access considerations.

## Quick Navigation

For common tasks, this guide provides direct links to the most relevant sections:

**System Monitoring:**
- Monitor system health → [Dashboard](#dashboard) section
- View real-time logs → [Logs](#logs-viewer) section
- View recordings → [Recordings](#recordings) section

**Agent Management:**
- Set up a new runner → [Agents → Provisioning Tab](#agents-provisioning-tab) section
- Set up a new listener → [Agents → Provisioning Tab](#agents-provisioning-tab) section
- Monitor runner status → [Agents → Runners Tab](#agents-runners-tab) section
- Monitor listener status → [Agents → Listeners Tab](#agents-listeners-tab) section

**Challenge Management:**
- Add a new challenge → [Challenges → Create Challenge Tab](#challenges-create-challenge-tab) section
- Import multiple challenges → [Challenges → Import from YAML Tab](#challenges-import-from-yaml-tab) section
- Enable/disable a challenge → [Challenges → Live Status Tab](#challenges-live-status-tab) section
- Test a challenge (Trigger Now) → [Challenges → Live Status Tab](#challenges-live-status-tab) section
- Edit/delete challenges → [Challenges → Manage Challenges Tab](#challenges-manage-challenges-tab) section

**System Administration:**
- Add admin user → [Users](#users) section
- Set up Discord webhooks → [Webhooks](#webhooks) section
- Pause/resume system → [System Controls](#system-controls) section
- Configure conference settings → [System Controls](#system-controls) section

**Troubleshooting:**
- Diagnose issues → [Advanced Topics](#advanced-topics) section

## Getting Help

If you need additional information beyond this guide, several other resources are available:

- **[Challenge Management Guide](Challenge-Management)** - Detailed challenge configuration information
- **[Runner Setup Guide](Runner-Setup)** - Runner agent installation and configuration
- **[Listener Setup Guide](Listener-Setup)** - Listener agent installation and configuration
- **[API Reference](API-Reference)** - Programmatic access to the system
- **[Architecture Overview](Architecture)** - How the UI interacts with the backend
- **[Troubleshooting Guide](Troubleshooting)** - Common issues and solutions
- **[Configuration Reference](Configuration-Reference)** - Advanced setup options

## Next Steps

**First-time users:**
- Start with the [Web Interface Overview](#web-interface-overview) to familiarize yourself with navigation and authentication
- Review the [Agents](#agents) section to understand runner and listener provisioning
- Explore the [Challenges](#challenges) section to learn about challenge lifecycle management

**Event preparation:**
- Configure [System Controls](#system-controls) including conference name and operating hours
- Set up [Webhooks](#webhooks) for Discord notifications
- Create [Users](#users) for your team members
- Import challenges via [Challenges → Import from YAML](#challenges-import-from-yaml-tab)

**Troubleshooting:**
- Check [Logs](#logs-viewer) for error messages and diagnostic information
- Review [Advanced Topics](#advanced-topics) for performance tuning and common issues
- Consult the [Troubleshooting Guide](Troubleshooting) for detailed solutions
