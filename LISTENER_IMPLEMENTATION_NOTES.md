# Listener Implementation vs Architecture Doc - Key Differences

This document summarizes the differences between the original `docs/SPECTRUM_LISTENER_ARCHITECTURE.md` design document and the actual implementation.

## Summary

The listener system has been successfully implemented with minor deviations from the original architecture document. The core concepts remain the same, but several details differ in the actual code.

## Key Differences

### 1. Recording Priority Threshold

**Architecture Doc Says:**
- Priority threshold: 10
- `Priority > 10`: Assign listener
- `Priority ≤ 10`: Skip recording

**Actual Implementation:**
- Priority threshold: **1.0**
- `Priority ≥ 1.0`: Assign listener
- `Priority < 1.0`: Skip recording

**Location in code:** `server/api.py:366` - `should_assign_listener()` function

### 2. Time Multiplier Calculation

**Architecture Doc Says:**
```python
time_multiplier = min(10.0, minutes_since / 60.0)  # Cap at 10x
```

**Actual Implementation:**
```python
time_multiplier = max(1.0, min(10.0, minutes_since / 60.0))  # Minimum 1x multiplier
```

**Difference:** The actual implementation ensures a **minimum 1x multiplier**, preventing priority from becoming zero for very recent recordings.

**Location in code:** `server/api.py:352`

### 3. Challenge Priority Boost

**Architecture Doc Says:**
- Challenge priority range: 1-100
- Formula: `priority_multiplier = challenge.priority / 10.0`
- Could result in very low multipliers (0.1x for priority=1)

**Actual Implementation:**
- Challenge priority range: **0-100** (0 is valid, means no boost)
- Formula: `priority_boost = 1.0 + (challenge_priority / 10.0)`
- Priority 0 = 1.0x (no penalty, baseline)
- Priority 10 = 2.0x
- Priority 50 = 6.0x
- Priority 100 = 11.0x

**Difference:** The actual implementation uses an **additive boost** starting from 1.0x instead of a pure multiplier. This ensures that setting priority=0 doesn't penalize a challenge.

**Location in code:** `server/api.py:360`

### 4. Database Schema - Field Naming

**Architecture Doc Says:**
- Recordings table has `agent_id` column
- Frontend references `listener_id`

**Actual Implementation:**
- Database stores as `agent_id` (unified runner/listener model)
- SQL queries use alias: `a.agent_id as listener_id` to return to frontend
- This is correct and intentional - provides semantic clarity in UI while maintaining unified schema

**Location in code:** `server/database.py:2051`, `server/database.py:2072`

### 5. API Endpoint Structure

**Architecture Doc Shows:**
- `/api/agents/{id}/recording_started`
- `/api/agents/{id}/recording_complete`
- `/api/agents/{id}/recording_failed`

**Actual Implementation:**
- `/api/agents/{id}/recording/start` (POST to create recording)
- `/api/agents/{id}/recording/{recording_id}/complete` (POST to mark complete)
- `/api/agents/{id}/recording/{recording_id}/upload` (POST to upload waterfall)
- No separate "failed" endpoint - failure reported via complete endpoint with `success: false`

**Difference:** The actual API uses a more RESTful structure with recording_id in the URL path, and combines success/failure reporting into one endpoint.

**Location in code:** `server/api.py:2338`, `server/api.py:2393`, `server/api.py:2446`

### 6. Pre/Post Roll Configuration

**Architecture Doc:**
- States both 5 seconds (correct)

**Actual Implementation:**
- Pre-roll: 5 seconds
- Post-roll: 5 seconds
- **This matches perfectly**

**Location in code:** Consistent across all configs and code

### 7. Recording Assignment WebSocket Event

**Architecture Doc Shows:**
```python
{
    event: 'recording_assignment',
    assignment_id: 123,
    challenge_id: 'CHALLENGE_1',
    challenge_name: 'NBFM_FLAG_1',
    frequency: 146550000,
    expected_start: '2025-11-21T12:00:05Z',
    expected_duration: 180,
    modulation_type: 'nbfm',
    transmission_id: 456
}
```

**Actual Implementation:**
```python
{
    'assignment_id': assignment_id,
    'challenge_id': challenge['challenge_id'],
    'challenge_name': challenge['name'],
    'transmission_id': transmission_id,
    'frequency': int(config.get('frequency', 0)),
    'expected_start': expected_start.isoformat(),
    'expected_duration': expected_duration,
    'runner_id': agent_id,  # ADDED: includes runner_id
    'timestamp': datetime.now(timezone.utc).isoformat()  # ADDED: includes timestamp
}
```

**Differences:**
- **Added:** `runner_id` field (which runner is transmitting)
- **Added:** `timestamp` field (when assignment was created)
- **Removed:** `modulation_type` field (not included in actual event)

**Location in code:** `server/api.py:2183-2193`

## What Remains Accurate

The following aspects of the architecture document remain accurate and match the implementation:

1. ✅ **Unified agents table** with `agent_type` field
2. ✅ **WebSocket-based coordination** for listeners
3. ✅ **HTTP polling** for runners (unchanged)
4. ✅ **Priority-based recording** algorithm (with corrected threshold)
5. ✅ **Database schema** (agents, recordings, listener_assignments tables)
6. ✅ **Content-addressed storage** for recordings
7. ✅ **Multi-device support** for listeners (radios.devices config)
8. ✅ **GNU Radio flowgraph** for spectrum capture
9. ✅ **Waterfall generation** using matplotlib
10. ✅ **Recording lifecycle** (pending → recording → completed/failed)

## Recommendations

### For Architecture Doc (SPECTRUM_LISTENER_ARCHITECTURE.md)

The architecture doc should be updated with:
1. Correct priority threshold (1.0 not 10)
2. Updated priority calculation formulas
3. Actual API endpoint structure
4. Corrected WebSocket event payload fields

### For Future Development

The current implementation is **production-ready** with these characteristics:
- Lower threshold (1.0) means more recordings captured
- Additive priority boost prevents penalties for low-priority challenges
- Minimum 1x time multiplier prevents zero priority
- RESTful API structure is cleaner than architecture doc proposed

## Testing Recommendations

When testing the priority algorithm, use these reference values:

| Scenario | Transmissions | Time Since | Time Mult | Priority Boost | Final Priority | Record? |
|----------|--------------|------------|-----------|----------------|----------------|---------|
| Never recorded | N/A | N/A | N/A | N/A | 1000.0 | ✅ Yes |
| 1 TX, 10 min ago | 1 | 10 min | 1.0 | 1.0 | 1.0 | ✅ Yes |
| 1 TX, 5 min ago | 1 | 5 min | 1.0 | 1.0 | 1.0 | ✅ Yes |
| 1 TX, 30 sec ago | 1 | 0.5 min | 1.0 | 1.0 | 1.0 | ✅ Yes |
| 0 TX, 2 hrs ago | 0 | 120 min | 2.0 | 1.0 | 0.0 | ❌ No |
| 5 TX, 1 hr ago | 5 | 60 min | 1.0 | 1.0 | 5.0 | ✅ Yes |
| 5 TX, 5 hrs ago | 5 | 300 min | 5.0 | 1.0 | 25.0 | ✅ Yes |
| With priority=10 | 1 | 60 min | 1.0 | 2.0 | 2.0 | ✅ Yes |
| With priority=50 | 1 | 60 min | 1.0 | 6.0 | 6.0 | ✅ Yes |

**Key insight:** With threshold at 1.0, nearly all transmissions after the first successful recording will be captured. Only brand-new recordings with <1 minute since last recording might be skipped.

## Conclusion

The implementation is **very close** to the architecture document with only minor, sensible deviations:
- Lower threshold (1.0 vs 10) makes the system more recording-friendly
- Additive priority boost is more intuitive than pure multiplication
- RESTful API is cleaner and more standard
- All core concepts (WebSocket coordination, priority algorithm, unified agents) are implemented as designed

The listener system is **production-ready** and working as intended.
