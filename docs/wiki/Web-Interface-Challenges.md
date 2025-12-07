# Challenge Management

The Manage Challenges page provides a unified interface for monitoring, creating, importing, editing, and controlling your challenges. This combines real-time monitoring with configuration management in a single location.

![Screenshot of Challenge Management Page](/docs/images/challenges_page_recordings.png "Challenge Management")

## Overview

The Manage Challenges page organizes functionality across four tabs, each serving a distinct purpose. The Live Status tab enables monitoring and control of active challenges in real-time. The Create Challenge tab provides a form-based interface for creating individual challenges with guided validation. The Import from YAML tab supports batch import of challenges from YAML files with file upload capability. The Manage Challenges tab allows viewing, editing, and deleting existing challenges through an intuitive interface.

When deciding which tab to use, consider your specific needs. Use the Live Status tab for monitoring challenge execution, enabling or disabling challenges, and triggering transmissions on demand. Choose the Create Challenge tab when adding one challenge at a time with step-by-step guidance. Select the Import from YAML tab for batch operations, migration tasks, or automation workflows. Use the Manage Challenges tab when you need to edit existing challenges or remove old ones from the system.

For comprehensive documentation on challenge configuration beyond the web interface, consult the Challenge Management Guide.

## Live Status Tab

The Live Status tab serves as the primary interface for real-time monitoring and control of challenge execution. The interface automatically refreshes every 15 seconds to maintain current information. Toggle switches provide immediate enable and disable control. Manual trigger controls allow on-demand transmission requests. The interface displays real-time status updates as challenges transition through states. Transmission count tracking shows historical execution data. A reload from config functionality enables loading challenges from the configuration file without restarting the server.

### Displayed Information

The interface displays comprehensive information for each challenge. The Challenge Name field shows the unique identifier used throughout the system. The Modulation field indicates the modulation type, such as CW, NBFM, SSB, or FHSS. The Frequency field displays the transmission frequency in hertz, automatically formatted as megahertz for readability.

The Status field shows the current challenge state using color-coded tags for quick recognition. A queued status displayed in green indicates the challenge is waiting for its delay period to elapse before becoming available. A waiting status shown in orange means the challenge is ready to be assigned to an available runner. An assigned status using the default styling indicates the challenge is currently being executed by a runner. A disabled status shown in gray means the challenge is not active and will not be queued for transmission.

The Enabled field provides a toggle switch to activate or deactivate the challenge. Enabled challenges will be queued for transmission according to their delay settings, while disabled challenges will not be queued regardless of other configuration.

The TX Count field displays the number of times the challenge has been transmitted since the server started. This counter updates in real-time as transmissions complete, providing historical execution data. The Last TX field shows the timestamp of the most recent transmission, formatted as relative time such as "2 minutes ago". This timestamp updates automatically to reflect the current time relationship.

### Actions Available

The Reload from Config button reloads challenges from the server-config.yml file. This operation adds new challenges defined in the config file without affecting database-stored challenges. Use this function when you have added challenges to the configuration file and want to make them available without restarting the server.

The Enable/Disable toggle switch provides immediate control over challenge activation. Click the switch to activate or deactivate a challenge. Enabled challenges enter the transmission queue according to their delay settings. Disabled challenges are skipped and will not be queued for transmission. Changes take effect immediately without requiring any additional confirmation or server restart.

The Trigger Now button manually queues the challenge for immediate transmission. This action bypasses the delay timer, moving the challenge directly to the "waiting" state. The next available compatible runner will execute it based on frequency capabilities and availability. Use this function for testing challenges, conducting demonstrations, or manually controlling transmission timing. This action does not affect the regular scheduling cycle, which continues independently based on the configured delay settings.

### Challenge Workflow

Challenges progress through a defined lifecycle that ensures controlled and predictable operation. Initially, a challenge exists in the disabled state, where it exists in the system but is inactive. When activated, the challenge enters the enabled state and joins the transmission queue.

Once enabled, the challenge moves to the queued state, where it waits for a random delay period between the configured minimum and maximum delay values. After the delay period expires, the challenge transitions to the waiting state, becoming ready for assignment and available to compatible runners that meet its frequency requirements.

When a runner claims the task, the challenge enters the assigned state. The runner executes the transmission according to the challenge configuration. Upon completion, the challenge returns to the queued state, where it waits for another delay period before becoming available again.

This cycle repeats continuously for enabled challenges, providing automated and controlled challenge distribution. Disabling a challenge at any point removes it from the cycle until re-enabled.

## Create Challenge Tab

The Create Challenge tab provides a structured interface for creating individual challenges using a guided form with built-in validation. Dynamic form fields adapt based on the selected modulation type, ensuring you only see relevant configuration options. Built-in validation checks required fields before allowing submission. File upload capabilities support audio and binary files directly through the interface. Modulation-specific parameter configuration ensures correct settings for each challenge type. Public field visibility configuration allows control over what information appears on the public dashboard.

### Workflow

The challenge creation process follows a logical sequence. Begin by entering basic information including the challenge name and modulation type. Select a frequency mode and configure the frequency according to your needs. Configure the challenge content by entering flag text or uploading a file. Set timing parameters including minimum and maximum delay values and priority level. Configure public dashboard visibility by selecting which fields should be visible to participants. If applicable to your modulation type, configure modulation-specific settings. When all configuration is complete, click the "Create Challenge" button to add the challenge to the system.

### Frequency Mode Selection

ChallengeCtl provides three frequency modes for flexible challenge configuration, each suited to different operational requirements.

Single Frequency Mode allows you to specify an exact transmission frequency in megahertz. The frequency input accepts values with 0.001 MHz precision, equivalent to 1 kHz resolution. The valid range spans from 1 to 6000 MHz. Use this mode when you want consistent and predictable frequency allocation for a challenge. For example, you might use 146.550 MHz for the 2m calling frequency.

Named Ranges Mode enables selection of one or more predefined frequency ranges from a dropdown menu. These ranges are defined in server-config.yml under the frequency_ranges section. The system randomly selects a frequency from the chosen ranges on each transmission, providing dynamic frequency allocation. Multiple ranges can be selected to create wider frequency distribution across different bands. The dropdown displays human-friendly names such as "2 Meter Ham Band" for easy recognition. Click the "Reload" button to refresh the list if ranges are added to the configuration. Use this mode for dynamic frequency allocation within specific amateur radio or licensed bands.

Manual Range Mode allows specification of custom minimum and maximum frequencies in megahertz. Both fields accept values with 0.001 MHz precision for fine-grained control. Each field supports the full range from 1 to 6000 MHz. The system randomly selects a frequency within your specified range on each transmission. Use this mode for custom frequency bands that are not included in the predefined ranges. For example, you might specify 146.000 MHz to 146.100 MHz for a narrow custom range.

Frequency information displays differently in tables based on the mode selected. Single frequency challenges show the frequency in megahertz, such as "146.550 MHz". Named range challenges display differently depending on how many ranges are selected. A single range shows the display name in a blue tag, such as "2 Meter Ham Band". Multiple ranges show "N ranges" in a blue tag with a tooltip that reveals all range names, such as "2 ranges" with tooltip text showing "2 Meter Ham Band, 70 Centimeter Ham Band". Manual range challenges show the range in megahertz with a "Custom:" prefix in an orange tag, such as "Custom: 146.000-148.000 MHz".

On the public dashboard, single frequency challenges display the exact frequency. Named range challenges show human-friendly range names in blue with text wrapping optimized for projector visibility. Manual range challenges show the frequency range in megahertz.

### Priority Field

The priority field accepts values ranging from 0 to 100, where a higher number indicates higher priority. Challenges with higher priority values are transmitted first when multiple challenges are waiting for assignment. The default priority is 0, representing normal priority. Use higher priority values for time-sensitive or important challenges that should be transmitted preferentially.

### Public Dashboard Visibility

The public dashboard visibility settings control which fields are visible to participants viewing the public interface. Available fields include name, modulation, frequency, status, and last transmission time. The default configuration displays name, modulation, frequency, and status. This feature allows you to control what information participants can see, enabling customization of the public experience based on your event requirements.

### Example Use Case

The Create Challenge tab excels at several common scenarios. Creating a new NBFM challenge during an active CTF event allows quick addition of content without interrupting operations. Testing different CW speeds helps find the right difficulty level for participants. Quickly adding a challenge without editing YAML files streamlines operations during live events.

## Import from YAML Tab

The Import from YAML tab enables batch import of multiple challenges from a YAML configuration file. This interface supports uploading a YAML file with challenge definitions, uploading associated media files such as WAV audio or binary data, automatic file path mapping between references and uploads, detailed import statistics and error reporting, and API documentation for automation workflows.

### Workflow

The import process follows a straightforward sequence. Begin by preparing a YAML file containing your challenge definitions according to the documented format. Click "Select YAML File" and choose your prepared file from your local filesystem. Optionally, click "Add Files" to upload media files referenced in your YAML configuration. Click "Import Challenges" to begin the import process. Review the import results, which show the number of challenges added, updated, and any errors encountered.

### File Handling

The system uses content-addressed storage for efficient file management. Files are uploaded and stored by their SHA-256 hash, ensuring deduplication and integrity verification. The system automatically maps uploaded files to challenge configurations based on filename references. If your YAML references "example.wav" and you upload a file named "example.wav", the system automatically links them together without requiring manual hash specification.

### Example Use Case

The Import from YAML tab supports several important workflows. Migrating challenges from server configuration to database storage enables runtime management without server restarts. Sharing challenge sets between ChallengeCtl instances facilitates collaboration and standardization across multiple events. Version-controlling challenges in git and importing from the repository enables proper change management and historical tracking. Restoring from backup allows rapid recovery after system failures or data loss.

## Manage Challenges Tab

The Manage Challenges tab provides comprehensive tools for viewing, editing, and deleting existing challenges. The interface presents a table view of all configured challenges with filter and search capabilities. A JSON editor enables advanced configuration changes directly in the interface. Delete operations include confirmation dialogs to prevent accidental data loss.

### Displayed Information

The table displays essential information for each challenge. The challenge name column shows the unique identifier. The modulation type column indicates the RF modulation scheme in use. The frequency column displays transmission frequency formatted as megahertz or gigahertz as appropriate. The status column shows whether the challenge is enabled or disabled using color-coded tags. The transmission count column displays the cumulative number of transmissions.

### Actions Available

The Refresh List button reloads challenges from the database, ensuring the display reflects current state. Use this after importing or creating challenges elsewhere to see the latest additions.

The Edit button opens a JSON editor dialog displaying the complete challenge configuration. Make changes directly to the JSON structure as needed. Click "Save" to apply your changes to the database. The interface validates JSON syntax before saving to prevent configuration corruption.

The Delete button removes a challenge permanently from the system. A confirmation dialog prevents accidental deletion by requiring explicit confirmation. This operation deletes the challenge configuration and transmission history. Referenced media files are not deleted, as other challenges may reference the same files through content-addressed storage.

### Example Use Case

The Manage Challenges tab supports several common operational needs. Adjusting minimum and maximum delay values during an event allows fine-tuning of transmission frequency based on participant feedback. Changing frequency settings after testing ensures correct operation before enabling for participants. Removing old or unused challenges keeps the system clean and focused. Copying configuration to create similar challenges accelerates creation of challenge sets with common characteristics.

## API Automation

The Import from YAML tab includes comprehensive documentation for API-based automation, enabling integration with external tools and workflows.

A cURL example demonstrates the HTTP interface:

```bash
curl -X POST http://localhost:8080/api/challenges/import \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE" \
  -F "yaml_file=@challenges.yml" \
  -F "example_voice.wav=@/path/to/example_voice.wav"
```

A Python example shows programmatic access:

```python
import requests

url = "http://localhost:8080/api/challenges/import"
files = {
    'yaml_file': open('challenges.yml', 'rb'),
    'example_voice.wav': open('example_voice.wav', 'rb'),
}
cookies = {'session': 'YOUR_SESSION_COOKIE'}
headers = {'X-CSRF-Token': 'YOUR_CSRF_TOKEN'}

response = requests.post(url, files=files, cookies=cookies, headers=headers)
print(response.json())
```

API automation supports several important use cases. CI/CD pipeline integration enables automated challenge deployment as part of your development workflow. Automated challenge rotation allows programmatic scheduling of challenge availability. Dynamic challenge generation from scripts enables creating challenges based on algorithms or external data sources. Remote challenge management facilitates administration from automated tools and monitoring systems.

## Best Practices

Several best practices help ensure smooth challenge management operations.

When creating challenges, use descriptive names that indicate difficulty and modulation type, such as "NBFM_EASY_1" rather than generic names like "FLAG1". Start challenges in the disabled state, test using the "Trigger Now" function to verify correct operation, then enable for automated transmission. Set appropriate delays based on event duration to balance participant exposure with resource utilization. Verify that the configured frequency falls within the frequency limits of at least one available runner.

When importing challenges, test YAML file syntax before importing to catch errors early. Keep YAML files under version control for change tracking and rollback capability. Upload all referenced media files together with the YAML to ensure complete configuration. Review import results carefully for errors that might indicate configuration problems.

When managing challenges, disable challenges rather than delete them during active events to preserve the option to re-enable if needed. Back up configuration before making bulk edits to enable recovery from mistakes. Use JSON validation tools when editing configuration directly to prevent syntax errors. Test changes with "Trigger Now" before re-enabling for automated transmission to verify correct operation.

When managing files, use meaningful filenames that indicate content and purpose, such as "flag_morse_slow.wav". Keep media files organized in directories for easier management. Do not delete files that might be used by multiple challenges, as content-addressed storage enables safe file sharing. Track file hashes for deduplication to identify when different challenges reference the same content.

## Typical Workflow

The unified Manage Challenges interface streamlines challenge management through an integrated workflow. Use the Create Challenge or Import from YAML tabs to add challenges to the system. Configure timing, priority, and public visibility settings to match your event requirements. Switch to the Live Status tab to monitor execution in real-time. Use the Live Status tab to enable, disable, or trigger challenges as needed during operations. Use the Manage Challenges tab to edit or delete existing challenges when configuration changes are required.

This unified approach eliminates the need to switch between separate pages for configuration and monitoring, improving operational efficiency.

## Troubleshooting

When a challenge refuses to transmit, start by checking the Manage Challenges Live Status tab for the challenge state. Verify that at least one runner is online and enabled, as challenges cannot transmit without available runners. Check that runner frequency limits include the challenge frequency, as frequency mismatch prevents assignment. Look for errors in the Logs page that might indicate configuration or execution problems. Try manual trigger from the Live Status tab to test whether the challenge can execute on demand.

## Related Guides

For detailed challenge configuration information beyond the web interface, consult the [Challenge Management](Challenge-Management) guide. For ensuring runners can execute challenges, see the [Agents Management](Web-Interface-Runners) guide. To view spectrum recordings and waterfall images, refer to the [Recordings Web Interface](Web-Interface-Recordings) guide. To monitor transmission activity, refer to the [Dashboard](Web-Interface-Dashboard) guide. For debugging challenge issues through log analysis, see the [Logs](Web-Interface-Logs) guide.
