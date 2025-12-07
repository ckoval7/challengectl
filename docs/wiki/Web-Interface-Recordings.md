# Recordings Web Interface

This guide covers the web interface features for viewing spectrum recordings and waterfall images captured by listener agents.

## Overview

The Recordings interface provides comprehensive visualization of spectrum recordings captured by listener agents during challenge transmissions. Listeners automatically record RF transmissions based on priority calculations, generating waterfall images that provide visual verification of signal quality, frequency accuracy, and transmission characteristics.

The interface delivers several key capabilities. Waterfall visualization displays high-quality spectrum waterfall images for each recording. Recording history maintains a complete history of all recordings per challenge. Inline preview provides quick access to recent recordings directly from the Challenges page without navigation. Detailed metadata shows frequency, duration, timestamps, and listener information for each recording. Status tracking monitors recording success, failures, and in-progress captures. A modal viewer provides full-screen waterfall image viewing with detailed metadata overlay.

## Accessing Recordings

The web interface provides two main paths to access listener recordings, each optimized for different workflows.

### Recording History Page (Full View)

The Recording History page provides a comprehensive view of all recordings for a specific challenge, showing complete historical data and metadata. To access this page, navigate to Manage Challenges and select the Live Status tab. Click the expand arrow next to any challenge row to reveal additional details. Click the "View All X Recordings" link at the bottom of the expanded section to open the full recording history. Alternatively, navigate directly to /recordings/{challenge_id} in your browser if you know the challenge ID.

### Inline Recordings (Quick Preview)

The Challenges page provides quick access to the most recent recordings without requiring navigation away from your current view. To access inline recordings, navigate to Manage Challenges and select the Live Status tab. Click the expand arrow next to any challenge to reveal its details. View the first three most recent recordings in an inline grid display. Click any waterfall image to open the full-screen viewer for detailed examination.

## Recording History Page

The Recording History page displays comprehensive information about a specific challenge and all its associated recordings.

### Challenge Information Card

The challenge information card displays key details about the selected challenge. The challenge name field shows the unique identifier used throughout the system. The modulation field indicates the type of RF modulation, such as CW, NBFM, SSB, or FHSS. The frequency field displays the transmission frequency formatted as megahertz or gigahertz as appropriate. The status field shows whether the challenge is enabled or disabled using color-coded tags for quick recognition. The total transmissions field provides a cumulative count of all transmissions for this challenge. The total recordings field shows the number of recordings that have been captured. The last transmission field displays the timestamp of the most recent transmission for temporal reference.

### Recordings Grid

All recordings display in a responsive grid layout that automatically adapts to screen size. The grid uses automatic sizing with a minimum card width of 300 pixels. Cards expand to fill available space efficiently. A hover effect provides visual feedback when the cursor moves over recording cards.

Each recording card displays comprehensive information. The recording ID appears at the top, using a format like "Recording #42" for easy identification. A status tag uses color-coding to indicate recording state. Green tags marked "Success" indicate completed recordings. Yellow tags marked "Warning" indicate recordings in progress. Red tags marked "Danger" indicate failed recordings. The listener ID identifies which listener captured this specific recording. The frequency shows the transmission frequency for this recording. The duration displays the length of the recording in seconds, including pre-roll and post-roll buffers. The started timestamp shows when the recording began. The completed timestamp shows when the recording finished, if it has completed. The waterfall thumbnail provides a preview image at 300 pixels height, clickable to enlarge. For failed recordings, an error message displays in a red alert box explaining what went wrong.

### Waterfall Thumbnails

Waterfall thumbnails use specific display characteristics for optimal preview. The thumbnail maintains a fixed height of 300 pixels while spanning the full width of its container card. Object-fit cover mode displays the top portion of the waterfall image. A hover effect provides slight scaling to 102 percent to indicate interactivity. Clicking any thumbnail opens the full-screen modal viewer for detailed examination.

The thumbnail displays the top portion of the waterfall because waterfall images flow from top (most recent) to bottom (oldest). This means the thumbnail shows the end of the transmission, which often proves most visually interesting and diagnostic.

### Empty State

When no recordings exist for a challenge, the interface displays a helpful empty state. An empty state illustration provides visual context. A message explains "No recordings available for this challenge yet." Additional text indicates that listeners need to be online and the priority threshold must be met for recordings to occur.

## Inline Recordings View

The Challenges page provides quick access to recent recordings without requiring navigation to a separate page.

### Accessing Inline View

To access the inline recordings view, navigate to Manage Challenges and select the Live Status tab. Locate the challenge you want to examine in the list. Click the expand arrow in the leftmost column of the challenge row. The row expands to reveal a recordings section with recent captures.

### What's Displayed

The recordings section displays several elements for quick reference. A section header labeled "Recordings" identifies the content area. The first three most recent recordings appear in grid format, matching the style of the full Recording History page. Recording cards use the same format as the full page, showing waterfall thumbnails at 300 pixels height along with complete metadata including listener, frequency, duration, and timestamps. Status tags indicate the state of each recording.

When more than three recordings exist for the challenge, a "View All" link appears. This link displays text in the format "View All {count} Recordings" with an arrow, making the total count visible. Clicking this link navigates to the full Recording History page for comprehensive access.

This inline view provides several benefits. Quick verification occurs without page navigation, saving time during active monitoring. The latest recording appears immediately for rapid assessment. Recent recordings can be compared side-by-side for trend analysis. Minimal disruption to the challenge management workflow ensures efficient operations.

### Loading States

The interface provides clear feedback during data loading. While loading recordings, an animated loading spinner icon appears with text reading "Loading recordings..." to indicate activity. After loading completes, either the recordings grid appears with available data, or a "No recordings available" message displays if none exist.

## Waterfall Image Modal

The modal viewer provides a full-screen view of waterfall images with comprehensive metadata for detailed analysis.

### Opening the Modal

To open the modal viewer, click any waterfall thumbnail in the Recording History page or any waterfall thumbnail in the inline recordings view. The image enlarges to a modal dialog occupying 90 percent of the viewport width for detailed examination.

### Modal Components

The modal header displays a title in the format "Recording #{id} - Waterfall" to identify the specific recording. A close button marked with an X appears in the top-right corner for dismissing the modal.

The metadata section displays recording details in a two-column grid format for easy reading. This section shows the challenge name, listener ID that captured the recording, frequency of transmission, duration of the recording, start timestamp, and completion timestamp if available.

The waterfall image displays at full resolution for detailed analysis. Maximum width is 100 percent of the modal container. Height scales automatically to maintain the correct aspect ratio. A border and rounded corners provide clean visual presentation. The content scrolls if the image height exceeds the viewport.

The background uses a light gray color from the Element Plus color system variable. This provides contrast for the metadata section and maintains consistency with the overall design system.

### Typical Waterfall Characteristics

Waterfall images have specific dimensional and visual characteristics. Width typically measures approximately 1000 pixels representing frequency bins across the capture bandwidth. Height varies based on recording duration, with a 10-second recording producing approximately 200 pixels and a 3-minute recording producing approximately 3600 pixels. The aspect ratio is optimized for frequency readability across the captured spectrum.

The color scheme follows a standard spectrum representation. Colors progress from blue through green and yellow to red, indicating increasing power levels. Dark blue or black background represents the noise floor. Bright colors indicate strong signals. The horizontal axis represents frequency, centered on the transmission frequency. The vertical axis represents time, with the top showing the most recent data and the bottom showing the oldest.

Visual elements within the waterfall provide diagnostic information. The signal appears as a colored stripe or pattern indicating transmission activity. Signal width indicates bandwidth of the transmission. Color intensity indicates signal strength relative to the noise floor. Clear start and stop boundaries show the pre-roll and post-roll buffer periods. Frequency offset labeling appears in megahertz for reference.

## Recording Status Indicators

Recordings can have three distinct status states, each indicated by color-coded tags for quick recognition.

### Success (Green Tag)

A completed status indicates successful recording. This means the recording was captured successfully from start to finish. The waterfall image was generated without errors. The image was uploaded to the server successfully. The recording is now available for viewing through the interface.

Visual indicators include a green tag displaying "completed" text. The waterfall thumbnail displays normally. All metadata fields are populated with complete information.

### Warning (Yellow Tag)

A recording or assigned status indicates work in progress. This means the recording is currently in progress with the listener actively capturing spectrum data. The waterfall has not yet been generated as the capture is ongoing. This represents a temporary state that typically lasts less than five minutes.

Visual indicators include a yellow tag displaying the current status text. No thumbnail appears since the recording is incomplete. Only partial metadata is available, typically showing just the started timestamp.

### Danger (Red Tag)

A failed status indicates an error occurred during recording. This means the recording encountered an error preventing completion. Waterfall generation failed due to technical issues. Upload to the server failed. An SDR device issue prevented capture.

Visual indicators include a red tag displaying "failed" text. No thumbnail appears due to the failure. An error message appears in a red alert box explaining the failure. Common error messages include "SDR device not available" when another process is using the SDR or the device is disconnected, "Failed to generate waterfall" when GNU Radio or Matplotlib encounters an error, "Upload timeout" when network issues prevent file transfer, and "GNU Radio flowgraph error" when configuration or device parameters are invalid.

## Understanding Recording Priority

Not every transmission is recorded, as the server uses a priority algorithm to decide which transmissions warrant capture while balancing resource utilization.

### Priority Factors

Never-recorded challenges receive the highest priority at 1000. This ensures all challenges have at least one recording on first opportunity, providing baseline documentation for every challenge.

Transmissions since the last recording influence priority through a count-based factor. More transmissions since the last recording increases priority proportionally. The formula multiplies transmission count by a time multiplier. This naturally balances recording frequency with system load.

Time since last recording applies a multiplier that increases over time. The time multiplier formula calculates as maximum of 1.0 and minimum of 10.0, based on minutes since last recording divided by 60. Minimum multiplier is 1.0 immediately after recording. Maximum multiplier of 10.0 applies after sufficient time has passed. This prevents any challenge from going too long without a recording.

Challenge priority settings allow manual prioritization. Configuration uses a 0 to 100 scale per challenge. Conversion to boost multiplier adds 1.0 to the priority divided by 10. Priority 0 equals 1.0 times multiplier with no change. Priority 10 equals 2.0 times multiplier. Priority 50 equals 6.0 times multiplier. This allows manual prioritization of important challenges.

### Priority Threshold

The default threshold for recording assignment is 1.0. When priority is at or above the threshold of 1.0, a recording is assigned to an available listener. The listener receives a WebSocket notification with recording parameters. A waterfall will be generated for the transmission.

When priority is below the threshold of 1.0, recording is skipped for this transmission. The challenge was recorded recently and doesn't require immediate capture. Listener resources are conserved for higher-priority captures.

### Why Not Record Everything

Priority-based recording serves several important purposes. Resource efficiency recognizes that listeners cannot capture every transmission. With 10 or more challenges transmitting 10 times per hour each, continuous recording would produce over 100 recordings per hour, overwhelming storage and processing capacity.

Storage conservation addresses the fact that waterfall images average approximately 300 kilobytes each. Continuous recording would rapidly consume disk space.

Diminishing returns recognizes that recording the same challenge every six minutes provides little new information. Periodic sampling captures representative data without excessive redundancy.

Balanced coverage ensures all challenges get recorded periodically rather than focusing exclusively on the most frequently transmitted challenges. This provides comprehensive documentation across the entire challenge set.

The result is that each challenge is recorded every few hours or after several transmissions, providing representative spectrum samples without overwhelming system resources.

## Navigation and Workflow

### Typical Workflows

Several common workflows demonstrate effective use of the listener web interface.

To verify a new challenge, navigate to Manage Challenges and select the Live Status tab. Find your newly created challenge in the list. Trigger a transmission using the "Trigger Now" button to queue it immediately. Wait 2 to 5 minutes for the recording to complete, as this includes transmission time, processing, and upload. Expand the challenge row to view inline recordings. View the waterfall thumbnail inline to verify the signal appears as expected without requiring additional navigation.

To compare recordings over time, click the challenge expand arrow to reveal details. Click "View All Recordings" to access the full history page. Scroll through the recordings grid to examine multiple captures. Click thumbnails to open the modal viewer for detailed examination. Compare signal characteristics across recordings to identify frequency drift, power changes, or other anomalies that might indicate configuration or hardware issues.

To debug transmission issues, navigate to the Dashboard to see any failed transmissions in the recent activity feed. Go to Manage Challenges and select the Live Status tab. Find the problematic challenge in the list. View recordings to verify several key aspects. Confirm the signal is present, indicating transmission is actually occurring. Verify the frequency is correct and matches configuration. Check that signal strength is adequate for participants to receive. Ensure modulation characteristics look correct for the challenge type. If no signal is visible in the waterfall, check runner logs for transmission errors.

To generate documentation, navigate to the Recording History page for each challenge you want to document. Open the waterfall modal for the best-quality recording of each challenge. Take a screenshot using your operating system's screenshot tool, or right-click and save the image directly. Use these waterfall images for documentation, write-ups, or reference materials. The metadata is preserved for later reference to technical details.

### Quick Access

The interface provides several navigation aids for efficient workflow. Breadcrumb navigation on the Recording History page includes a "Back to Challenges" button that returns you to the Challenges page when clicked, preserving your place in the workflow.

Direct URL access supports bookmarking and sharing. Recording History pages use URLs in the format /recordings/{challenge_id}. You can bookmark specific challenge recordings for quick access. Share URLs with team members for collaboration.

## Recording Metadata Explained

Each recording includes detailed metadata for analysis and troubleshooting purposes.

### Listener ID

The listener ID appears in a format like "listener-1", serving as the unique identifier of the listener agent that captured this recording. This information proves useful for several purposes. You can compare recordings from different listeners to understand geographic or antenna differences. It helps identify hardware-specific issues that affect only certain listeners. You can track listener performance over time. It aids in debugging antenna or SDR problems specific to particular hardware.

When multiple listeners are deployed, you may see different listeners capturing different recordings. This provides geographic diversity if listeners are in different physical locations. It offers redundancy serving as backup if one listener fails. It enables load distribution by spreading recording work across multiple listener systems.

### Frequency

The frequency appears in a format like "146.550 MHz", indicating the center frequency of the recording. This should match the challenge's configured frequency under normal circumstances. Mismatches indicate configuration issues requiring investigation.

For challenges using frequency ranges rather than fixed frequencies, each recording shows the actual frequency used for that specific transmission. Frequency varies per transmission within the defined range. The waterfall shows offset from the center frequency for reference.

### Duration

The duration appears in a format like "185.0s", indicating the total recording length in seconds. This includes pre-roll buffer time, typically 5 seconds before transmission starts. It includes the actual transmission duration. It includes post-roll buffer time, typically 5 seconds after transmission ends. The actual transmission time equals the total duration minus pre-roll and post-roll times.

Pre-roll and post-roll buffers serve important purposes. Pre-roll captures transmission start timing, ensuring nothing is missed at the beginning. Post-roll captures transmission end, verifying complete transmission occurred. They show the noise floor before and after transmission for comparison. They provide context for signal analysis and troubleshooting.

### Timestamps

Timestamps appear in formats like "2025-11-24 10:30:00" for started and "2025-11-24 10:33:05" for completed. The started timestamp indicates when the listener began recording, corresponding to the pre-roll start time. The completed timestamp shows when the waterfall image was uploaded to the server. The time difference approximately equals the duration plus processing time, typically 5 to 10 seconds for image generation and upload.

These timestamps prove useful for several purposes. You can correlate recordings with transmission logs to verify timing. They help verify timing synchronization between components. They identify delays or lags in the recording pipeline. They help troubleshoot missed recordings by comparing expected and actual times.

### Image Path

Although not displayed in the UI, the image path is stored in the database for internal reference. The format follows the pattern files/waterfalls/{recording_id}.png, providing a consistent storage scheme. This path serves several purposes. It indicates the server-side storage location for the file. It is referenced by the /api/recordings/{id}/image endpoint for retrieval. Content-addressed storage by recording ID enables efficient management. It enables efficient caching and content delivery network distribution.

## Troubleshooting

### No Recordings Showing

When no recordings appear for a challenge, several possible causes should be investigated.

No listeners online prevents recording assignment. Check the Agents page and select the Listeners tab. Verify at least one listener shows "Online" status. Confirm the WebSocket shows "Connected" status, as this is required for recording assignments.

Priority too low causes the server to skip recording. The challenge may have been recorded recently, causing priority to fall below threshold. The server skipped this transmission based on the priority algorithm. Wait for priority to increase as more transmissions occur and time passes.

No transmissions yet means there's nothing to record. The challenge must transmit before it can be recorded. Check the Dashboard for transmission activity to verify challenges are executing. Trigger a manual transmission to test the recording pipeline.

Listener frequency mismatch prevents assignment due to hardware limitations. The challenge frequency may be outside the listener's frequency capabilities. Check the listener configuration for frequency_limits settings. Ensure overlap exists between challenge frequency and listener capabilities.

Solutions include enabling at least one listener through the Agents page. Verify the listener WebSocket connection shows "Connected" status. Wait for the challenge to transmit multiple times to increase priority. Check listener logs for assignment messages indicating the system attempted to assign recordings.

### Waterfall Image Not Loading

When waterfall thumbnails or modal images fail to load, several symptoms and causes should be considered.

Symptoms include the thumbnail showing a broken image icon. The modal shows blank space or an error message. The recording status shows "completed" despite the missing image.

Files missing from the server cause loading failures. The image upload may have failed during recording. Files might have been deleted manually from storage. Storage directory permissions issues prevent file access.

Network issues prevent image delivery. The server may be unreachable from the client. Firewall rules might be blocking image requests. Proxy timeout settings may be too short for large images.

Large image timeout affects long recordings. Very tall waterfall images from long recordings require more time to transfer. Slow network connections exacerbate the problem. Server timeout configuration may be too aggressive.

Solutions include checking the browser console for HTTP errors indicating the specific problem. Verify files exist on the server using ls files/waterfalls/{recording_id}.png. Check server logs for image serving errors. Increase server timeout settings for large images. Test manually using curl http://server/api/recordings/{id}/image to isolate the issue.

### Recording Failed

Failed recordings display specific symptoms and error messages that guide troubleshooting.

Symptoms include a red "failed" status tag on the recording card. An error message appears in the recording card. No waterfall image is available for viewing.

"SDR device not available" indicates another process is using the SDR, preventing exclusive access. The device may be disconnected from the USB bus. USB power issues might be preventing device enumeration. Solutions include checking listener logs for detailed error information and restarting the listener process to reset device state.

"Failed to generate waterfall" points to GNU Radio errors during capture or processing. Matplotlib import errors prevent image generation. Insufficient memory prevents processing large FFT data. Solutions include checking listener system resources for memory and CPU constraints and reviewing logs for detailed error messages.

"Upload timeout" indicates network issues between listener and server. The server may be overloaded and unable to accept uploads quickly. The image file may be too large for current timeout settings. Solutions include checking network connectivity and bandwidth, increasing timeout values in configuration, and reducing recording duration to decrease file size.

"GNU Radio flowgraph error" suggests configuration problems. Invalid device strings prevent device initialization. Unsupported sample rates cause device errors. Gain values outside the device range cause initialization failures. Solutions include validating listener configuration against device capabilities and testing the device using osmocom_fft to verify basic operation.

### Recordings Section Won't Expand

When clicking the expand arrow produces no result, several causes should be investigated.

Symptoms include clicking the expand arrow with no visible response. No recordings section appears after clicking. No error message displays to explain the failure.

JavaScript errors prevent the interface from functioning. Check the browser console for error messages. Reload the page using Ctrl+F5 to clear cached code.

API request failing prevents data retrieval. Check the Network tab in browser DevTools for failed requests. Look for failed /api/challenges/{id}/recordings requests specifically. Check server logs for API endpoint errors.

Empty response provides no data to display. No recordings may exist yet for this challenge. The API might be returning an empty array correctly. The interface should show "No recordings available" in this case.

Solutions include hard refreshing the page using Ctrl+Shift+R to clear all caches. Checking the browser console for JavaScript errors. Verifying API endpoint accessibility using browser DevTools. Reviewing server logs for API-related errors.

### Poor Waterfall Quality

When waterfall images show poor signal visibility, several factors may be responsible.

Symptoms include the signal being barely visible against the noise floor. Excessive noise obscuring the signal. Washed out colors preventing clear signal identification. Unclear frequency axis labeling.

Low RF gain causes weak signal capture. Listener gain settings may be too low for the signal strength. The signal falls below the noise floor in the recording. Solutions include increasing gain in the listener configuration to values like 40 to 50 dB for better sensitivity.

Poor antenna selection or placement affects signal quality. The antenna may not be resonant at the transmission frequency. Poor antenna placement or orientation reduces signal strength. Solutions include using an appropriate antenna designed for the frequency band being monitored.

RF interference overwhelms the SDR receiver. Strong local signals may be overloading the receiver. Harmonics from nearby transmitters create false signals. Solutions include moving the listener to a different location with less interference, adding filtering to remove out-of-band signals, and adjusting gain to prevent overload.

Sample rate mismatch affects signal representation. Sample rate too narrow causes the signal to be cut off at the edges. Sample rate too wide makes the signal appear thin in the waterfall. Solutions include matching the transmitter sample rate, typically 2 MHz for most challenges.

## Related Guides

For configuring and deploying listener agents, see the Listener Setup guide. To view listener status and WebSocket connection state, consult the Agents Management guide. For managing challenges and triggering transmissions, review the Challenge Management guide. To monitor transmission activity system-wide, see the Dashboard guide. For understanding the recording priority algorithm in detail, refer to the Architecture documentation. For common issues and solutions beyond the UI, consult the Troubleshooting Guide.
