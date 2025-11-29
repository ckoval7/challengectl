# Web Interface Guide

This guide covers the ChallengeCtl web interface, explaining how to monitor system status, manage challenges and runners, and control system operation through the browser-based dashboard.

## Overview

The ChallengeCtl web interface provides a comprehensive view of your RF challenge distribution system. It allows administrators to monitor system health, manage runners and challenges, view real-time logs, and control system operation without needing to edit configuration files or restart services.

### Key Features

The web interface delivers real-time monitoring through live updates via WebSocket connections, ensuring administrators always have current information. Challenge management functionality enables you to enable, disable, and manually trigger challenges as needed. The interface supports complete challenge configuration, allowing you to create, import, edit, and delete challenges directly through the web UI. Runner control capabilities let you monitor runner status and manage their connections effectively. Log streaming provides real-time access to logs from both the server and all connected runners. User administration features allow comprehensive management of admin accounts and credentials. System controls enable pausing and resuming operations system-wide. The conference countdown feature provides live countdown timers with support for daily hour cycling. Finally, auto-pause scheduling automatically manages system pause and resume based on configured daily operating hours.

## Documentation Sections

This guide is organized into several sections for easier navigation, divided into getting started materials, core features, and advanced topics.

### Getting Started

The Web Interface Overview section covers the fundamentals of the web interface, including how to access and log in, session management, user menu options, navigation, and security best practices. This section serves as your starting point for understanding the interface.

### Core Features

The Dashboard section explains the statistics panel, recent transmissions feed, and conference settings card. This is your primary monitoring interface for overall system health.

The Runners Management section covers the runner list and status display, available runner actions including enable, disable, and kick operations, guidance on when to disable versus kick runners, real-time updates, and troubleshooting procedures for runner issues.

The Challenge Management section details the Live Status tab for monitoring and control, the Create Challenge tab for form-based creation, the Import from YAML tab for batch import operations, the Manage Challenges tab for editing and deleting challenges, API automation capabilities, best practices for challenge management, and typical workflows.

The User Management section explains the user list and available operations, procedures for adding users, different user account types, permission management, password and TOTP management, built-in security features, and common workflows for user administration.

The System Controls section covers the differences between pause and disable operations, configuration reload functionality, and comprehensive conference settings including conference name and countdown, daily operating hours, auto-pause functionality, configuration workflows, and best practices.

The Logs Viewer section describes log display and color coding, filtering options by source and level, auto-scroll, search, and export capabilities, common log patterns to recognize, and techniques for troubleshooting with logs.

### Advanced Topics

The Advanced Topics section explores real-time updates via WebSocket, tips and best practices for effective interface usage, troubleshooting techniques through the UI, performance optimization strategies, browser compatibility information, API access methods, and mobile access considerations.

## Quick Navigation

For common tasks, this guide provides direct links to the most relevant sections. To monitor system health, refer to the Dashboard section. For adding a new challenge, see the Create Challenge section. To import multiple challenges at once, consult the Import from YAML section. Enabling or disabling a challenge is covered in the Live Status section. Testing a challenge using the Trigger Now function is also documented in the Live Status section. Managing runners is covered in the Runners Management section. Adding a new admin user is explained in the Add User section. Pausing the system is detailed in the System Controls section. Setting up conference hours is covered in the Conference Settings section. Viewing logs is explained in the Logs Viewer section. Finally, troubleshooting issues is addressed in the Advanced Topics section under Troubleshooting.

## Getting Help

If you need additional information beyond this guide, several other resources are available. The Challenge Management Guide provides detailed challenge configuration information. The API Reference explains programmatic access to the system. The Architecture Overview helps you understand how the UI interacts with the backend. The Troubleshooting Guide addresses common issues and their solutions. Finally, the Configuration Reference covers advanced setup options for more complex deployments.

## Next Steps

If you are using the interface for the first time, start with the Web Interface Overview to familiarize yourself with the basics. If you are setting up for an event, review the Challenge Management and System Controls sections to prepare your configuration. When you need to troubleshoot issues, check the Logs Viewer and Advanced Topics sections for diagnostic techniques. For managing users and permissions, see the User Management section.
