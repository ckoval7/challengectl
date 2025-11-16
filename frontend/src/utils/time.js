/**
 * Time formatting utilities for consistent timezone handling
 */

/**
 * Parse a timestamp from the server and convert to local time.
 * Handles both ISO format and SQLite TIMESTAMP format.
 *
 * @param {string} timestamp - Timestamp from server
 * @returns {Date} Date object in local timezone
 */
export function parseServerTime(timestamp) {
  if (!timestamp) return null

  // If the timestamp doesn't have a timezone indicator, assume it's UTC
  // SQLite CURRENT_TIMESTAMP returns format: "2025-11-16 17:30:45"
  // We need to treat this as UTC
  if (!timestamp.includes('Z') && !timestamp.includes('+') && !timestamp.includes('T')) {
    // SQLite format - add 'Z' to indicate UTC
    return new Date(timestamp.replace(' ', 'T') + 'Z')
  }

  // ISO format with timezone - parse normally
  return new Date(timestamp)
}

/**
 * Format a timestamp as local time string (HH:MM:SS)
 *
 * @param {string} timestamp - Timestamp from server
 * @returns {string} Formatted time string
 */
export function formatTime(timestamp) {
  if (!timestamp) return 'Never'
  const date = parseServerTime(timestamp)
  return date.toLocaleTimeString()
}

/**
 * Format a timestamp as local date and time string
 *
 * @param {string} timestamp - Timestamp from server
 * @returns {string} Formatted date and time string
 */
export function formatDateTime(timestamp) {
  if (!timestamp) return 'Never'
  const date = parseServerTime(timestamp)
  return date.toLocaleString()
}
