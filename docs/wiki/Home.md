# ChallengeCtl Wiki

Welcome to the ChallengeCtl documentation. ChallengeCtl is an SDR (Software Defined Radio) challenge distribution system designed for RFCTF (RF Capture The Flag) competitions. It coordinates the transmission of radio signals across multiple modulation types through networked SDR devices, providing mutual exclusion guarantees and automatic failover capabilities.

## What is ChallengeCtl?

ChallengeCtl enables CTF organizers to manage radio frequency challenges by distributing transmission tasks to networked SDR devices (runners). The system ensures that each challenge is transmitted exactly once at a time, prevents duplicate transmissions, and automatically handles device failures through intelligent task requeuing.

## System Components

ChallengeCtl consists of three main components:

- **Server**: A centralized controller that manages challenge scheduling, runner coordination, and provides a REST API and web interface
- **Runner**: A client application that runs on devices with SDR hardware, executes transmission tasks, and reports status back to the server
- **Frontend**: A Vue.js web application for monitoring system status, managing challenges, and viewing real-time logs

## Documentation

### Getting Started
- **[Quick Start Guide](Quick-Start)** - Get up and running in minutes
- **[Server Setup](Server-Setup)** - Complete guide to deploying the server
- **[Runner Setup](Runner-Setup)** - Complete guide to configuring and running SDR clients

### Usage Guides
- **[Web Interface Guide](Web-Interface-Guide)** - Managing ChallengeCtl through the web dashboard
- **[Using ChallengeCtl CLI](ChallengeCtl-CLI)** - Working with the standalone command-line interface
- **[Configuration Reference](Configuration-Reference)** - Detailed configuration options for server and runner

### Technical Documentation
- **[Architecture Overview](Architecture)** - How the system works under the hood
- **[API Reference](API-Reference)** - REST API endpoints and WebSocket events
- **[Challenge Development](Challenge-Development)** - Creating new challenge types and modulations
- **[Implementing Permissions](Implementing-Permissions)** - Guide to adding new permissions to the system
- **[Troubleshooting](Troubleshooting)** - Common issues and solutions

## Key Features

- **Mutual Exclusion**: Prevents duplicate transmissions through pessimistic database locking
- **Automatic Failover**: Detects failed runners and automatically reassigns their tasks
- **File Synchronization**: Content-addressed file distribution with SHA-256 verification
- **Real-Time Monitoring**: WebSocket-based live updates for challenge status and logs
- **Multi-Modulation Support**: Supports CW, ASK, NBFM, SSB, FHSS, POCSAG, LRS, FreeDV, and Paint modulations
- **Security**: API key authentication for runners and TOTP 2FA for admin users

## Quick Links

- [GitHub Repository](https://github.com/ckoval7/challengectl)
- [Report an Issue](https://github.com/ckoval7/challengectl/issues)

## Support

For questions, issues, or contributions, please visit the [GitHub repository](https://github.com/ckoval7/challengectl) or open an issue in the issue tracker.
