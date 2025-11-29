# Dashboard

The dashboard provides an overview of system status and recent activity.

## Statistics Panel

The top section of the dashboard displays key metrics that provide a quick assessment of system health. The Total Runners metric shows the number of registered runners, including both online and offline units. The Active Runners metric indicates how many runners are currently online and available, with color-coded indicators to quickly assess system health. A green indicator signifies a healthy system with sufficient active runners, a yellow indicator warns that some runners are offline, and a red indicator alerts you that no runners are currently available.

The Total Challenges metric displays the number of configured challenges in the system, while the Enabled Challenges metric shows how many challenges are currently active and eligible for transmission. The Total Transmissions metric provides a cumulative count of all completed transmissions since the server started, giving you a sense of overall system activity.

## Recent Transmissions Feed

The lower section of the dashboard shows real-time transmission activity, providing visibility into what is currently happening in your RF challenge system. Each entry in the feed displays several key pieces of information. The Challenge column shows the name of the transmitted challenge, while the Runner column identifies which runner executed the transmission. The Frequency column displays the transmission frequency in hertz, automatically formatted as megahertz for readability. The Modulation column indicates the type of modulation used for the transmission. The Status column provides a success or failure indicator, and the Timestamp column shows when the transmission completed.

Status indicators use clear visual cues to communicate transmission outcomes. A green checkmark indicates a successful transmission, while a red X marks a failed transmission. Hovering over a failed transmission reveals additional error details to aid in troubleshooting.

The feed updates automatically as transmissions complete, using WebSocket events to deliver real-time information without requiring page refreshes. This ensures you always see the most current activity in your system.

## Conference Settings Card

The Conference Settings card on the Dashboard allows you to configure conference-specific features including daily operating hours, countdown timers, and automatic pause and resume functionality. For detailed information about configuring and using conference settings, see the System Controls Guide.

## Related Guides

For managing and controlling runners, see the Runners Management guide. To manage challenges and their configuration, consult the Challenge Management guide. For detailed information about conference settings, refer to the System Controls guide. To view detailed logs for troubleshooting and monitoring, see the Logs Viewer guide.
