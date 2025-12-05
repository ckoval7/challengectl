#!/usr/bin/env python3
"""
Unit tests for device matching improvements.

Tests the new serial-based device matching logic in DeviceManager.
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from device_manager import DeviceManager

# Mock osmosdr to prevent it from hanging during tests
sys.modules['osmosdr'] = MagicMock()


class TestDeviceSerialResolution:
    """Test serial number resolution for device matching."""

    def test_resolve_serial_returns_serial_for_long_string(self):
        """Test that long alphanumeric names are returned as-is (already serials)."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Long hex string should be returned as-is
        serial = dm.resolve_device_serial('bladerf', '1234567890abcdef')
        assert serial == '1234567890abcdef'

    def test_resolve_serial_maps_index_to_serial(self):
        """Test that numeric index is mapped to serial via hardware enumeration."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Mock enumerate_device_serials to return test serials
        with patch.object(dm, 'enumerate_device_serials', return_value=['abc123', 'def456']):
            serial = dm.resolve_device_serial('bladerf', '0')
            assert serial == 'abc123'

            serial = dm.resolve_device_serial('bladerf', '1')
            assert serial == 'def456'

    def test_resolve_serial_returns_none_for_out_of_range_index(self):
        """Test that out-of-range index returns None."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Mock enumerate_device_serials to return only one device
        with patch.object(dm, 'enumerate_device_serials', return_value=['abc123']):
            serial = dm.resolve_device_serial('bladerf', '1')  # Index 1, but only 0 exists
            assert serial is None

    def test_enumerate_hackrf_serials(self):
        """Test HackRF serial enumeration."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Mock subprocess output from hackrf_info
        mock_stdout = """Found HackRF
Board ID Number: 2 (HackRF One)
Firmware Version: 2018.01.1
Part ID Number: 0xa000cb3c 0x00524752
Serial number: 0x000000000000a06063dc2f5b3f5f

Found HackRF
Board ID Number: 2 (HackRF One)
Firmware Version: 2018.01.1
Part ID Number: 0xa000cb3c 0x00524753
Serial number: 0x000000000000b07063dc2f5b3f60
"""

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_stdout)

            serials = dm.enumerate_device_serials('hackrf')

            # Should normalize (remove leading zeros)
            assert len(serials) == 2
            assert serials[0] == 'a06063dc2f5b3f5f'
            assert serials[1] == 'b07063dc2f5b3f60'

    def test_enumerate_bladerf_serials(self):
        """Test BladeRF serial enumeration."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Mock subprocess output from bladeRF-cli -p
        mock_stdout = """Backend:        libusb
  Serial:       a4c20e3f12345678
  USB Bus:      1
  USB Address:  4

Backend:        libusb
  Serial:       b5d30f4023456789
  USB Bus:      1
  USB Address:  5
"""

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_stdout)

            serials = dm.enumerate_device_serials('bladerf')

            assert len(serials) == 2
            assert 'a4c20e3f12345678' in serials
            assert 'b5d30f4023456789' in serials

    def test_rtlsdr_numeric_serial_not_treated_as_index(self):
        """Test that RTL-SDR numeric serials (like '1090') are not treated as indices."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Common RTL-SDR serials: "1090", "00000001", etc.
        # These should be treated as serials, not device indices
        serial_1090 = dm.resolve_device_serial('rtlsdr', '1090')
        assert serial_1090 == '1090'  # Should return as-is, not try to enumerate

        serial_00000001 = dm.resolve_device_serial('rtlsdr', '00000001')
        assert serial_00000001 == '00000001'  # Should return as-is

    def test_rtlsdr_single_digit_treated_as_index(self):
        """Test that RTL-SDR single-digit numbers (0-9) are still treated as indices."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Mock enumerate_device_serials to return test serials
        with patch.object(dm, 'enumerate_device_serials', return_value=['1090', '00000001']):
            serial_0 = dm.resolve_device_serial('rtlsdr', '0')
            assert serial_0 == '1090'  # Should map index 0 → serial '1090'

            serial_1 = dm.resolve_device_serial('rtlsdr', '1')
            assert serial_1 == '00000001'  # Should map index 1 → serial '00000001'

    def test_rtlsdr_enumeration_failure_fallback(self):
        """Test that RTL-SDR falls back to serial matching when enumeration fails."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Mock enumerate_device_serials to return empty list (timeout/failure)
        with patch.object(dm, 'enumerate_device_serials', return_value=[]):
            # For multi-digit numbers (≥4 digits), should treat as serial instead of failing
            serial = dm.resolve_device_serial('rtlsdr', '1090')
            assert serial == '1090'  # Should fall back to treating as serial

            serial = dm.resolve_device_serial('rtlsdr', '00000001')
            assert serial == '00000001'  # Should fall back to treating as serial

    def test_enumerate_rtlsdr_serials_via_osmosdr(self):
        """Test RTL-SDR serial enumeration using osmosdr."""
        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        # Mock osmosdr to simulate RTL-SDR devices
        mock_osmosdr = MagicMock()

        # Create mock device objects with to_string() method
        mock_dev1 = MagicMock()
        mock_dev1.to_string.return_value = 'driver=rtlsdr,serial=00000001,label=Generic RTL2832U'

        mock_dev2 = MagicMock()
        mock_dev2.to_string.return_value = 'driver=rtlsdr,serial=1090,label=RTL-SDR Blog V3'

        mock_dev3 = MagicMock()
        mock_dev3.to_string.return_value = 'driver=hackrf,serial=abc123'  # Non-RTL device

        mock_osmosdr.device.find.return_value = [mock_dev1, mock_dev2, mock_dev3]

        # Patch osmosdr module
        with patch.dict('sys.modules', {'osmosdr': mock_osmosdr}):
            serials = dm.enumerate_device_serials('rtlsdr')

            # Should find 2 RTL-SDR devices (skip the HackRF)
            assert len(serials) == 2
            assert serials[0] == '00000001'
            assert serials[1] == '1090'


class TestDeviceMatching:
    """Test intelligent device matching based on serials."""

    def test_is_device_known_matches_by_serial(self):
        """Test that config device with index matches auto-detected device with serial."""
        # Config device: bladerf=0
        config_devices = [{
            'model': 'bladerf',
            'name': '0',
            'device_id': 0,
            'device_string': 'bladerf=0'
        }]

        dm = DeviceManager(config_devices, device_probe_interval=0, enable_auto_detection=False)

        # Mock serial resolution: index 0 -> serial abc123
        with patch.object(dm, 'resolve_device_serial', return_value='abc123'):
            # Auto-detected device with serial
            detected_device = {
                'model': 'bladerf',
                'name': 'abc123',
                'serial': 'abc123',
                'device_string': 'bladerf=abc123'
            }

            # Should match because index 0 resolves to abc123
            assert dm._is_device_known(detected_device) is True

    def test_is_device_known_no_match_different_serial(self):
        """Test that devices with different serials don't match."""
        config_devices = [{
            'model': 'bladerf',
            'name': '0',
            'device_id': 0,
            'device_string': 'bladerf=0'
        }]

        dm = DeviceManager(config_devices, device_probe_interval=0, enable_auto_detection=False)

        # Mock serial resolution: index 0 -> serial abc123
        with patch.object(dm, 'resolve_device_serial', return_value='abc123'):
            # Auto-detected device with different serial
            detected_device = {
                'model': 'bladerf',
                'name': 'xyz999',
                'serial': 'xyz999',
                'device_string': 'bladerf=xyz999'
            }

            # Should NOT match
            assert dm._is_device_known(detected_device) is False

    def test_is_device_known_serial_to_serial_match(self):
        """Test that serial-based config matches serial-based detection."""
        config_devices = [{
            'model': 'bladerf',
            'name': 'abc123',
            'device_id': 0,
            'device_string': 'bladerf=abc123'
        }]

        dm = DeviceManager(config_devices, device_probe_interval=0, enable_auto_detection=False)

        # Mock serial resolution: serial -> same serial
        with patch.object(dm, 'resolve_device_serial', return_value='abc123'):
            detected_device = {
                'model': 'bladerf',
                'name': 'abc123',
                'serial': 'abc123',
                'device_string': 'bladerf=abc123'
            }

            assert dm._is_device_known(detected_device) is True


class TestConfigDeviceEnrichment:
    """Test that configured devices are enriched with serials at startup."""

    def test_enrich_configured_devices_adds_serial(self):
        """Test that configured devices get serial field added."""
        config_devices = [{
            'model': 'bladerf',
            'name': '0',
            'device_id': 0
        }]

        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        with patch.object(dm, 'resolve_device_serial', return_value='abc123'):
            enriched = dm._enrich_configured_devices(config_devices)

            assert len(enriched) == 1
            assert enriched[0]['serial'] == 'abc123'
            assert enriched[0]['model'] == 'bladerf'
            assert enriched[0]['name'] == '0'

    def test_enrich_handles_missing_serial(self):
        """Test that devices that can't be resolved still get processed."""
        config_devices = [{
            'model': 'bladerf',
            'name': '1',  # Device offline/not connected
            'device_id': 0
        }]

        dm = DeviceManager([], device_probe_interval=0, enable_auto_detection=False)

        with patch.object(dm, 'resolve_device_serial', return_value=None):
            enriched = dm._enrich_configured_devices(config_devices)

            assert len(enriched) == 1
            assert enriched[0]['serial'] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
