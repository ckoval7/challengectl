# Listener Web UI

This guide covers the web interface features for viewing and managing spectrum listener recordings and waterfall images.

## Overview

The Listener Web UI provides comprehensive visualization of spectrum recordings captured by listener agents during challenge transmissions. Listeners automatically record RF transmissions based on priority, generating waterfall images that provide visual verification of signal quality, frequency accuracy, and transmission characteristics.

### Key Features

- **Waterfall Visualization**: High-quality spectrum waterfall images for each recording
- **Recording History**: Complete history of all recordings per challenge
- **Inline Preview**: Quick access to recent recordings directly from the Challenges page
- **Detailed Metadata**: Frequency, duration, timestamps, and listener information
- **Status Tracking**: Monitor recording success, failures, and in-progress captures
- **Modal Viewer**: Full-screen waterfall image viewer with detailed metadata

## Accessing Recordings

There are two main ways to access listener recordings in the web interface:

### 1. Recording History Page (Full View)

The Recording History page provides a comprehensive view of all recordings for a specific challenge.

**To access:**
1. Navigate to **Manage Challenges → Live Status** tab
2. Click the expand arrow (►) on any challenge row
3. Click **"View All X Recordings →"** link at the bottom of the expanded section
4. Or navigate directly to `/recordings/{challenge_id}` in your browser

### 2. Inline Recordings (Quick Preview)

The Challenges page provides quick access to the most recent recordings without leaving the page.

**To access:**
1. Navigate to **Manage Challenges → Live Status** tab
2. Click the expand arrow (►) next to any challenge
3. View the first 3 most recent recordings in an inline grid
4. Click any waterfall image to open the full-screen viewer

## Recording History Page

The Recording History page displays comprehensive information about a challenge and all its associated recordings.

### Challenge Information Card

Displays key information about the challenge:

**Fields Shown:**
- **Challenge Name**: Unique identifier
- **Modulation**: Type (CW, NBFM, SSB, FHSS, etc.)
- **Frequency**: Transmission frequency in MHz/GHz
- **Status**: Enabled/Disabled with color-coded tag
- **Total Transmissions**: Cumulative count of all transmissions
- **Total Recordings**: Number of recordings captured
- **Last Transmission**: Timestamp of most recent transmission

### Recordings Grid

All recordings are displayed in a responsive grid layout:

**Grid Layout:**
- Automatically adjusts to screen size
- Minimum card width: 400px
- Cards expand to fill available space
- Hover effect for visual feedback

**Card Contents:**
Each recording card shows:
- **Recording ID**: Unique identifier (e.g., "Recording #42")
- **Status Tag**: Color-coded status indicator
  - Green (Success): Recording completed successfully
  - Yellow (Warning): Recording in progress
  - Red (Danger): Recording failed
- **Listener ID**: Which listener captured this recording
- **Frequency**: Transmission frequency
- **Duration**: Length of recording in seconds (includes pre/post roll)
- **Started Timestamp**: When recording began
- **Completed Timestamp**: When recording finished (if completed)
- **Waterfall Thumbnail**: Preview image (400px height, click to enlarge)
- **Error Message**: Displayed for failed recordings

### Waterfall Thumbnails

**Thumbnail Display:**
- Fixed height: 400px
- Full width of card
- Object-fit: Cover (shows top portion of waterfall)
- Hover effect: Slight scale increase (1.02x)
- Click to open full-screen modal

**Why Top Portion?**
Waterfall images flow from top (most recent) to bottom (oldest), so the thumbnail shows the end of the transmission, which is often most visually interesting.

### Empty State

If no recordings exist for a challenge:
- Empty state illustration displayed
- Message: "No recordings available for this challenge yet."
- Indicates listeners need to be online and priority threshold met

## Inline Recordings View

The Challenges page provides quick access to recent recordings without navigating away.

### Accessing Inline View

**Steps:**
1. Navigate to **Manage Challenges → Live Status** tab
2. Locate the challenge you want to view
3. Click the **expand arrow** (►) in the leftmost column
4. The row expands to show recordings section

### What's Displayed

**Recordings Section:**
- **Section Header**: "Recordings"
- **First 3 Most Recent**: Shows up to 3 latest recordings in grid format
- **Recording Cards**: Same format as Recording History page
  - Waterfall thumbnail (400px height)
  - Metadata (listener, frequency, duration, timestamps)
  - Status tag
- **"View All" Link**: If more than 3 recordings exist
  - Text: "View All {count} Recordings →"
  - Links to full Recording History page

**Benefits:**
- Quick verification without page navigation
- See latest recording immediately
- Compare recent recordings side-by-side
- Minimal disruption to challenge management workflow

### Loading States

**While Loading:**
- Loading spinner icon (animated)
- Text: "Loading recordings..."

**After Loading:**
- Recordings grid appears
- Or "No recordings available" message if none exist

## Waterfall Image Modal

The modal viewer provides a full-screen view of waterfall images with detailed metadata.

### Opening the Modal

**How to Open:**
- Click any waterfall thumbnail in Recording History page
- Click any waterfall thumbnail in inline recordings view
- Image enlarges to modal dialog (90% viewport width)

### Modal Components

**Header:**
- Title: "Recording #{id} - Waterfall"
- Close button (X) in top-right

**Metadata Section:**
Displays recording details in a 2-column grid:
- Challenge name
- Listener ID
- Frequency
- Duration
- Start timestamp
- Completion timestamp (if available)

**Waterfall Image:**
- Full-resolution display
- Maximum width: 100% of modal
- Height: Auto-scaled to maintain aspect ratio
- Border and rounded corners for clean presentation
- Scrollable if image is very tall

**Background:**
- Light gray background (`--el-fill-color-light`)
- Provides contrast for metadata
- Consistent with Element Plus design system

### Typical Waterfall Characteristics

**Dimensions:**
- Width: ~1000 pixels (frequency bins)
- Height: Variable based on recording duration
  - 10 second recording: ~200 pixels
  - 3 minute recording: ~3600 pixels
- Aspect ratio optimized for frequency readability

**Color Scheme:**
- Blue → Green → Yellow → Red (increasing power)
- Dark blue/black background (noise floor)
- Bright colors indicate strong signals
- Horizontal axis: Frequency (centered on transmission frequency)
- Vertical axis: Time (top = most recent, bottom = oldest)

**Visual Elements:**
- Signal appears as colored stripe or pattern
- Width indicates bandwidth
- Color intensity indicates signal strength
- Clear start/stop boundaries show pre/post roll
- Frequency offset labeled in MHz

## Recording Status Indicators

Recordings can have three status states, indicated by color-coded tags:

### Success (Green Tag)

**Status:** `completed`

**Meaning:**
- Recording captured successfully
- Waterfall image generated
- Image uploaded to server
- Available for viewing

**Visual:**
- Green tag with "completed" text
- Waterfall thumbnail displayed
- All metadata populated

### Warning (Yellow Tag)

**Status:** `recording` or `assigned`

**Meaning:**
- Recording currently in progress
- Listener is actively capturing spectrum
- Waterfall not yet generated
- Temporary state (usually <5 minutes)

**Visual:**
- Yellow tag with status text
- No thumbnail (recording not complete)
- Partial metadata (started timestamp only)

### Danger (Red Tag)

**Status:** `failed`

**Meaning:**
- Recording encountered an error
- Waterfall generation failed
- Upload failed
- SDR device issue

**Visual:**
- Red tag with "failed" text
- No thumbnail displayed
- Error message in red alert box
- Common errors:
  - "SDR device not available"
  - "Failed to generate waterfall"
  - "Upload timeout"
  - "GNU Radio flowgraph error"

## Understanding Recording Priority

Not every transmission is recorded. The server uses a priority algorithm to decide which transmissions to capture:

### Priority Factors

**1. Never Recorded (Priority: 1000)**
- Highest priority
- Challenges never recorded are captured on first opportunity
- Ensures all challenges have at least one recording

**2. Transmissions Since Last Recording**
- More transmissions = higher priority
- Formula: `transmissions_count × time_multiplier`
- Naturally balances recording frequency with system load

**3. Time Since Last Recording**
- Older recordings increase priority over time
- Time multiplier: `max(1.0, min(10.0, minutes_since / 60.0))`
- Minimum 1x multiplier, increasing to 10x over time
- Prevents any challenge from going too long without a recording

**4. Challenge Priority Setting**
- Configurable per challenge (0-100 scale)
- Converts to boost: `1.0 + (challenge_priority / 10.0)`
- Priority 0 = 1.0x (no change), Priority 10 = 2.0x, Priority 50 = 6.0x
- Allows manual prioritization of important challenges

### Priority Threshold

**Default Threshold: 1.0**

**Above Threshold (Priority ≥ 1.0):**
- Recording is assigned
- Listener receives WebSocket notification
- Waterfall will be generated

**Below Threshold (Priority < 1.0):**
- Recording skipped for this transmission
- Challenge was recently recorded
- Listener resources conserved

### Why Not Record Everything?

**Reasons for Priority-Based Recording:**
1. **Resource Efficiency**: Listeners can't capture every transmission (10+ challenges × 10 transmissions/hour = 100+ recordings/hour)
2. **Storage Conservation**: Waterfall images are ~400 KB each
3. **Diminishing Returns**: Recording the same challenge every 6 minutes provides little new information
4. **Balanced Coverage**: Ensures all challenges get recorded periodically, not just popular ones

**Result:** Each challenge is recorded every few hours or after several transmissions, providing representative spectrum samples without overwhelming the system.

## Navigation and Workflow

### Typical Workflows

**Workflow 1: Verify New Challenge**
1. Navigate to **Manage Challenges → Live Status**
2. Find your new challenge
3. Trigger transmission with **"Trigger Now"** button
4. Wait 2-5 minutes for recording to complete
5. Expand the challenge row
6. View waterfall thumbnail inline
7. Verify signal appears as expected

**Workflow 2: Compare Recordings Over Time**
1. Click challenge expand arrow
2. Click **"View All Recordings →"**
3. Scroll through recordings grid
4. Click thumbnails to open modal viewer
5. Compare signal characteristics across recordings
6. Identify any frequency drift, power changes, or anomalies

**Workflow 3: Debug Transmission Issues**
1. Navigate to **Dashboard** to see failed transmissions
2. Go to **Manage Challenges → Live Status**
3. Find the problematic challenge
4. View recordings to verify:
   - Signal is present (transmission working)
   - Frequency is correct
   - Signal strength is adequate
   - Modulation looks correct
5. If no signal visible, check runner logs

**Workflow 4: Generate Documentation**
1. Navigate to Recording History page for each challenge
2. Open waterfall modal for best-quality recording
3. Take screenshot (or right-click → Save image)
4. Use for documentation, write-ups, or reference
5. Metadata is preserved for later reference

### Quick Access

**Breadcrumb Navigation:**
- Recording History page includes "← Back to Challenges" button
- Returns to Challenges page when clicked
- Preserves your place in the workflow

**Direct URL Access:**
- Recording History: `/recordings/{challenge_id}`
- Bookmark specific challenge recordings
- Share URLs with team members

## Recording Metadata Explained

Each recording includes detailed metadata for analysis and troubleshooting:

### Listener ID

**Example:** `listener-1`

**What it means:**
- Unique identifier of the listener agent that captured this recording
- Useful for:
  - Comparing recordings from different locations
  - Identifying hardware-specific issues
  - Tracking listener performance
  - Debugging antenna or SDR problems

**Multiple Listeners:**
If you have multiple listeners, you may see different listeners capturing different recordings. This provides:
- Geographic diversity (if listeners are in different locations)
- Redundancy (backup if one listener fails)
- Load distribution (spreads recording work across listeners)

### Frequency

**Example:** `146.550 MHz`

**What it means:**
- Center frequency of the recording
- Should match the challenge's configured frequency
- If mismatched, indicates configuration issue

**Frequency Ranges:**
For challenges using frequency ranges (not fixed frequency):
- Each recording shows the actual frequency used for that transmission
- Frequency varies per transmission within the defined range
- Waterfall shows offset from center frequency

### Duration

**Example:** `185.0s`

**What it means:**
- Total recording length in seconds
- Includes pre-roll (typically 5s before transmission)
- Includes post-roll (typically 5s after transmission)
- Actual transmission time = duration - pre_roll - post_roll

**Why Pre/Post Roll?**
- Captures transmission start (ensures nothing missed)
- Captures transmission end (verifies complete transmission)
- Shows noise floor before/after for comparison
- Provides context for signal analysis

### Timestamps

**Started:** `2025-11-24 10:30:00`
**Completed:** `2025-11-24 10:33:05`

**What they mean:**
- **Started**: When listener began recording (pre-roll start time)
- **Completed**: When waterfall image was uploaded
- Time difference ≈ duration + processing time (~5-10 seconds)

**Uses:**
- Correlate with transmission logs
- Verify timing synchronization
- Identify delays or lags
- Troubleshoot missed recordings

### Image Path

**Not displayed in UI, but stored in database**

**Format:** `files/waterfalls/{recording_id}.png`

**Purpose:**
- Server-side storage location
- Referenced by `/api/recordings/{id}/image` endpoint
- Content-addressed storage (by recording ID)
- Enables efficient caching and CDN distribution

## Troubleshooting

### No Recordings Showing

**Possible Causes:**
1. **No listeners online**
   - Check **Agents → Listeners** tab
   - Verify at least one listener shows "Online"
   - WebSocket should show "Connected"

2. **Priority too low**
   - Challenge was recently recorded
   - Server skipped this transmission
   - Wait for priority to increase (more transmissions, more time)

3. **No transmissions yet**
   - Challenge must transmit before it can be recorded
   - Check Dashboard for transmission activity
   - Trigger manual transmission to test

4. **Listener frequency mismatch**
   - Challenge frequency outside listener's capabilities
   - Check listener config `frequency_limits`
   - Ensure overlap with challenge frequency

**Solutions:**
- Enable at least one listener in Agents page
- Verify listener WebSocket connection
- Wait for challenge to transmit multiple times
- Check listener logs for assignment messages

### Waterfall Image Not Loading

**Symptoms:**
- Thumbnail shows broken image icon
- Modal shows blank or error
- Recording status is "completed"

**Possible Causes:**
1. **File missing from server**
   - Image upload failed
   - File was deleted manually
   - Storage directory permissions issue

2. **Network issue**
   - Server unreachable
   - Firewall blocking image requests
   - Proxy timeout

3. **Large image timeout**
   - Very tall waterfall (long recording)
   - Slow network connection
   - Server timeout

**Solutions:**
- Check browser console for HTTP errors
- Verify file exists: `ls files/waterfalls/{recording_id}.png`
- Check server logs for image serving errors
- Increase server timeout for large images
- Test with `curl http://server/api/recordings/{id}/image`

### Recording Failed

**Symptoms:**
- Red "failed" status tag
- Error message in recording card
- No waterfall image

**Common Error Messages:**

**"SDR device not available"**
- Another process using the SDR
- Device disconnected
- USB power issue
- Solution: Check listener logs, restart listener process

**"Failed to generate waterfall"**
- GNU Radio error
- Matplotlib import error
- Insufficient memory
- Solution: Check listener system resources, review logs

**"Upload timeout"**
- Network issue between listener and server
- Server overloaded
- Image too large
- Solution: Check network, increase timeout, reduce recording duration

**"GNU Radio flowgraph error"**
- Invalid device string
- Unsupported sample rate
- Gain out of range
- Solution: Validate listener config, test with `osmocom_fft`

### Recordings Section Won't Expand

**Symptoms:**
- Click expand arrow, nothing happens
- No recordings section appears
- No error message

**Possible Causes:**
1. **JavaScript error**
   - Check browser console
   - Reload page (Ctrl+F5)

2. **API request failing**
   - Check Network tab in browser DevTools
   - Look for failed `/api/challenges/{id}/recordings` request
   - Check server logs

3. **Empty response**
   - No recordings exist yet
   - API returning empty array
   - Should show "No recordings available" message

**Solutions:**
- Hard refresh page (Ctrl+Shift+R)
- Check browser console for errors
- Verify API endpoint is accessible
- Review server logs for API errors

### Poor Waterfall Quality

**Symptoms:**
- Signal barely visible
- Excessive noise
- Washed out colors
- Frequency axis unclear

**Possible Causes:**
1. **Low RF gain**
   - Listener gain setting too low
   - Signal below noise floor
   - Solution: Increase `gain` in listener config (try 40-50 dB)

2. **Poor antenna**
   - Antenna not resonant at frequency
   - Poor placement or orientation
   - Solution: Use appropriate antenna for frequency band

3. **RF interference**
   - Strong local signals overwhelming SDR
   - Harmonics from nearby transmitters
   - Solution: Move listener, add filtering, adjust gain

4. **Sample rate mismatch**
   - Sample rate too narrow (signal cut off)
   - Sample rate too wide (signal looks thin)
   - Solution: Match transmitter sample rate (typically 2 MHz)

## Related Guides

- [Listener Setup](Listener-Setup) - Configure and deploy listener agents
- [Agents Management](Web-Interface-Runners) - View listener status and WebSocket connection
- [Challenge Management](Web-Interface-Challenges) - Manage challenges and trigger transmissions
- [Dashboard](Web-Interface-Dashboard) - Monitor transmission activity
- [Architecture](Architecture) - Understanding recording priority algorithm
- [Troubleshooting](Troubleshooting) - Common issues and solutions
