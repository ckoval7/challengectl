# LRS Pager System Optimization

**Date:** 2025-11-25
**Status:** ⚠️ REQUIRES TESTING

## Summary

The LRS (Long Range Systems) pager transmission code has been optimized to eliminate unnecessary disk I/O operations. Previously, the system would generate a binary file (~2 KB), save it to disk, read it back, transmit it, and then delete the file on every transmission. This has been refactored to pass data directly in memory.

## Changes Made

### 1. `challenges/lrs_pager.py`
**Before:**
- Generated Manchester-encoded pager data
- Wrote binary file to disk (`./temp/lrs_XXXXXX.bin`)
- Used `struct.pack('f', ...)` to write 32-bit floats
- No return value

**After:**
- Generates Manchester-encoded pager data in memory
- Builds list of floats directly (`all_floats`)
- Returns list of ~540 float values
- No file I/O operations

**Modified lines:** 167-193

### 2. `challenges/lrs_tx.py`
**Before:**
- Accepted `binfile` parameter pointing to disk file
- Used `blocks.file_source()` to read from disk
- Had `-r/--binfile` command-line argument

**After:**
- Accepts `data` parameter (Python list of floats)
- Uses `blocks.vector_source_f()` for in-memory data
- Removed `-r/--binfile` argument
- Added `data` parameter to `main()` function

**Modified lines:** 27, 34, 61-62, 70, 81-87, 128-132, 149, 152

### 3. `runner/runner.py`
**Before:**
```python
# Generate random temp filename
randomstring = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
temp_dir = os.path.join(os.getcwd(), 'temp')
os.makedirs(temp_dir, exist_ok=True)
outfile = os.path.join(temp_dir, f"lrs_{randomstring}.bin")

# Write to disk
lrspageropts.outputfile = outfile
lrs_pager.main(options=lrspageropts)

# Read from disk and transmit
lrsopts.binfile = outfile
lrs_tx.main(options=lrsopts)

# Clean up
os.remove(outfile)
```

**After:**
```python
# Generate data in memory
pager_data = lrs_pager.main(options=lrspageropts)

# Transmit in-memory data
lrs_tx.main(options=lrsopts, data=pager_data)
```

**Modified lines:** 834-852

### 4. `challenges/lrs_tx.grc` (NEW)
- Created GNU Radio Companion source file for maintainability
- Targets GNU Radio 3.9+ (tested on 3.10)
- Documents the flowgraph structure
- Uses `blocks_vector_source_x` instead of `blocks_file_source`

## Benefits

1. **Performance:** Eliminates ~2 KB disk write/read per transmission
2. **Cleaner code:** Removed 7 lines of code, eliminated temp file management
3. **More robust:** No file permission issues, no leftover temp files
4. **Better architecture:** Direct memory-to-memory data flow
5. **Maintainable:** GRC file documents the flowgraph for future modifications

## Data Flow

### Before
```
lrs_pager.py → disk file (~2 KB) → lrs_tx.py (file_source) → GNU Radio → SDR
                  ↓
              os.remove()
```

### After
```
lrs_pager.py → memory (list of floats) → lrs_tx.py (vector_source) → GNU Radio → SDR
```

## Technical Details

- **Data format:** List of Python floats
- **Data size:** ~540 floats per pager (~2.1 KB in memory)
- **Values:** `0.0001` = binary 0, `1.0` = binary 1 (Manchester encoding)
- **GNU Radio block:** `blocks.vector_source_f(data, repeat=False, vlen=1, tags=[])`

## Testing Performed

- ✅ Python syntax validation (all files compile)
- ✅ Integration test with simulated device (file sink to /dev/null)
- ✅ Data generation: 540 floats with correct value range
- ✅ Flowgraph instantiation and execution

## ⚠️ REQUIRED: Real Hardware Testing

**@Dan - Please verify the following:**

1. **Basic transmission test:**
   - [ ] Start a runner with LRS challenges configured
   - [ ] Verify LRS pager transmissions are assigned and execute
   - [ ] Check runner logs for any errors
   - [ ] Confirm no `./temp/lrs_*.bin` files are created

2. **Functional test:**
   - [ ] Verify LRS pagers actually receive and respond to transmissions
   - [ ] Test with multiple pager IDs
   - [ ] Test with different alert types (functions 1, 4, 10)
   - [ ] Confirm transmission quality is unchanged

3. **Performance test:**
   - [ ] Monitor runner execution time for LRS challenges
   - [ ] Compare with baseline (if available)
   - [ ] Check for any memory issues during extended runs

4. **Edge cases:**
   - [ ] Test with `-v` verbose flag in challenge config
   - [ ] Test with `-k` printkey flag
   - [ ] Test with `-r` random flag
   - [ ] Test with multiple pager IDs in one transmission

## Rollback Instructions

If issues are found, revert with:
```bash
git checkout HEAD~1 -- challenges/lrs_pager.py challenges/lrs_tx.py runner/runner.py
git rm challenges/lrs_tx.grc
```

## Known Limitations

1. **GNU Radio vector_source behavior:** The `vector_source` block doesn't support runtime data updates. A new flowgraph instance must be created for each transmission. This matches the previous behavior where `file_source` was reopened for each transmission.

2. **No backward compatibility mode:** The old file-based interface has been completely removed. If needed for debugging, use git to temporarily revert to the previous implementation.

## Questions or Issues?

If you encounter any problems during testing:
1. Check runner logs for Python exceptions
2. Verify GNU Radio version is 3.9+ (tested on 3.10.9.2)
3. Compare transmission behavior with previous working version
4. Open an issue with logs and specific error messages

---

**Testing Status:** 🔴 Not yet tested on real hardware
**Approval Required:** Dan
**Next Steps:** Hardware verification, then merge to main
