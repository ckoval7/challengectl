[![Frontend CI](https://github.com/ckoval7/challengectl/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/ckoval7/challengectl/actions/workflows/frontend-ci.yml)
[![Backend CI](https://github.com/ckoval7/challengectl/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/ckoval7/challengectl/actions/workflows/backend-ci.yml)
[![WAV format check](https://github.com/rfhs/challengectl/actions/workflows/wav-format-check.yaml/badge.svg)](https://github.com/rfhs/challengectl/actions/workflows/wav-format-check.yaml)

# ChallengeCtlv2

**Distributed RF CTF Challenge Management That Just Works**

ChallengeCtl is a modern, distributed system for managing Software-Defined Radio (SDR) challenges in Capture The Flag (CTF) competitions. Gone are the days of manually editing CSV files, copying flags between machines, and hoping your challenges don't interfere with each other. ChallengeCtl brings significant coordination, real-time monitoring, and intelligent spectrum recording to RF CTF operations, making it effortless to run professional radio frequency competitions at scale.

## What Makes ChallengeCtl v2 Exciting

If you've used the original standalone version of ChallengeCtl, you'll immediately appreciate the transformation. The new distributed architecture means you can coordinate multiple SDR devices across different locations from a single web interface, watching transmissions happen in real-time with live status updates. Challenge files synchronize automatically using content-addressed storage, so there's no more manual copying or worrying about version mismatches. The intelligent spectrum recording system captures waterfall visualizations of your transmissions with priority-based scheduling. Setup is simpler, operations are more reliable, and scaling from one SDR to dozens requires no architectural changes.

## Key Features

**Distributed Architecture with Multi-Runner Coordination**: ChallengeCtl uses a centralized server to coordinate multiple remote SDR runners, allowing you to deploy transmitters across different locations while managing everything from a single point of control. The system scales effortlessly from a single device to dozens of runners without requiring any configuration changes.

**Self-Healing with Automatic Failover**: Stale assignments are automatically detected and requeued, runner heartbeat monitoring marks offline agents, and the system gracefully handles network failures with exponential backoff retry logic. Your CTF continues running even when individual components fail.

**Per-Antenna Configuration**: Multi-antenna devices like the BladeRF can configure different frequency limits, RF gain, and bias-T settings for each antenna. The runner automatically selects the appropriate antenna based on challenge frequency, optimizing RF performance across different bands.

**Comprehensive Monitoring and Logging**: Real-time log streaming aggregates output from the server and all connected agents into a single web interface with filtering by source and severity. The transmission history provides a complete audit trail of all challenge executions.

**Support for 8+ Modulation Types**: Challenges support NBFM (narrowband FM), SSB (single sideband), FreeDV (digital voice), POCSAG (paging), LRS (paging), CW (morse code), ASK (amplitude shift keying), FHSS (frequency hopping spread spectrum), and spectrum painting. Each modulation is implemented as a GNU Radio flowgraph for maximum flexibility.

**Real-Time Web Dashboard with Live Updates**: The Vue.js web interface uses WebSocket connections to deliver instant updates across all connected browsers. Watch challenge assignments, transmission completions, and agent status changes happen in real-time without ever refreshing the page.

**Intelligent Spectrum Recording**: Listener agents capture RF transmissions and generate waterfall images using priority-based scheduling. The system automatically decides which transmissions to record based on challenge priority, transmission history, and time elapsed since last capture, ensuring comprehensive coverage without wasting resources.

**Content-Addressed File Synchronization**: All challenge files use SHA-256 hashing for identification and verification. Runners automatically download and cache files on demand, with hash verification ensuring integrity. Multiple challenges can reference the same file without duplication.


## Supported Modulations

ChallengeCtl includes fire functions and GNU Radio flowgraphs for a wide variety of RF challenge types:

- **NBFM (Narrowband FM)**: Classic frequency modulation for audio flags
- **SSB (Single Sideband)**: Upper and lower sideband audio transmission
- **FreeDV**: Open-source digital voice mode for codec challenges
- **POCSAG**: Paging protocol messages using gr-mixalot
- **LRS**: Custom paging signal format
- **CW (Morse Code)**: Classic radiotelegraphy at configurable speeds
- **ASK (Amplitude Shift Keying)**: Simple on-off keying for binary data
- **FHSS (Frequency Hopping)**: Challenges that hop between frequencies
- **Spectrum Paint**: Visual image transmission in the waterfall using gr-paint

## Quick Start

### Prerequisites

- Python 3.9 or higher (Python 3.12 recommended)
- Node.js 20.x or higher (for web frontend development)
- GNU Radio 3.9 or higher with gr-osmosdr, gr-paint, and gr-mixalot (for runners)
- Compatible SDR hardware (HackRF One, BladeRF 2.0, USRP B200, or any gr-osmosdr device)

### Installation

Installation insctructions can be found in the [Quick Start Guide](docs/wiki/Quick-Start.md), [Server Setup Guide](docs/wiki/Server-Setup.md), and [Runner Setup Guide](docs/wiki/Runner-Setup.md).

## Architecture Overview

ChallengeCtl consists of four main components that work together to deliver distributed RF challenge management:

**Server**: A Flask-based REST API with SQLite database coordination, WebSocket broadcasting for real-time updates, and background task scheduling. The server assigns challenges to runners using pessimistic database locking to guarantee mutual exclusion, manages agent heartbeats, and coordinates spectrum recording assignments.

**Runner**: A Python client that polls the server for challenge assignments, executes transmissions using GNU Radio flowgraphs, and reports completion status. Runners cache challenge files locally using content-addressed storage and automatically select appropriate antennas based on frequency requirements.

**Listener**: A spectrum recording agent that connects via WebSocket to receive recording assignments, captures RF transmissions using GNU Radio, generates waterfall images from FFT data, and uploads results to the server for visualization in the web interface.

**Frontend**: A Vue.js single-page application with real-time updates via WebSocket, comprehensive agent and challenge management interfaces, live log streaming with filtering, and a dashboard showing system status and transmission statistics.

## Supported Hardware

ChallengeCtl has been tested and verified to work with the following SDR devices:

- [Nuand BladeRF 2.0 Micro](https://www.nuand.com/bladerf-2-0-micro/) - Multi-antenna support with per-antenna configuration
- [Great Scott Gadgets HackRF One](https://greatscottgadgets.com/hackrf/one/)

Any SDR device supported by gr-osmosdr should work for both transmission (runners) and reception (listeners), though these three platforms have been extensively tested in production RFCTF environments.

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Quick Start Guide](docs/wiki/Quick-Start.md) - Get up and running in minutes
- [Architecture Overview](docs/wiki/Architecture.md) - Understand how the system works
- [Server Setup](docs/wiki/Server-Setup.md) - Complete server installation and configuration
- [Runner Setup](docs/wiki/Runner-Setup.md) - Deploy and configure SDR runners
- [Listener Setup](docs/wiki/Listener-Setup.md) - Set up spectrum recording agents
- [Challenge Development](docs/wiki/Challenge-Development.md) - Create custom RF challenges
- [Challenge Management](docs/wiki/Challenge-Management.md) - Use the web UI to manage challenges
- [Web Interface Guide](docs/wiki/Web-Interface-Guide.md) - Navigate the dashboard and admin pages
- [Configuration Reference](docs/wiki/Configuration-Reference.md) - Complete YAML configuration options
- [API Reference](docs/wiki/API-Reference.md) - REST API documentation for automation
- [Troubleshooting](docs/wiki/Troubleshooting.md) - Common issues and solutions

## Testing and CI/CD

ChallengeCtl maintains comprehensive test coverage with continuous integration across multiple Python and Node.js versions:

**Backend Testing**: The server and database logic are tested using pytest with over 40% code coverage. Tests include unit tests for database operations, cryptographic utilities, and integration tests for end-to-end workflows. CI runs on Python 3.9, 3.12, and 3.13.

**Frontend Testing**: The Vue.js interface uses Vitest with Vue Test Utils, maintaining over 50% code coverage. Tests verify component behavior, user interactions, and WebSocket integration. CI validates compatibility with Node.js 20.x and 22.x.

**Quality Assurance**: The WAV format validation workflow ensures audio challenge files meet quality standards. All commits trigger automated testing with the results visible in the badges at the top of this README.

Run tests locally with `pytest tests/ -v` for backend tests or `cd frontend && npm run test` for frontend tests.

## License

ChallengeCtl is free software licensed under the GNU General Public License v3.0. You are free to use, modify, and distribute this software in accordance with the terms of the GPL v3. See the [LICENSE](LICENSE) file for complete details.

## Credits

ChallengeCtl is developed and maintained by the RFHS (Radio Frequency Hackers Sanctuary) community for use in RFCTF competitions. Special thanks to all contributors who have helped build, test, and improve the system through multiple CTF events.

If you're organizing an RF CTF or want to contribute to the project, visit our repository at [github.com/rfhs/challengectl](https://github.com/rfhs/challengectl) or join the RFHS community.
