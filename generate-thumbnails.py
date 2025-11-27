#!/usr/bin/env python3
"""
Generate thumbnails for existing recordings.

This script processes all recordings in the database that have images but no thumbnails,
generating 300x300 square thumbnails with top-aligned cropping.
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_path():
    """Get the path to the database file."""
    # Check if running from server directory
    if os.path.exists('server/challengectl.db'):
        return 'server/challengectl.db'
    # Check if running from root directory
    elif os.path.exists('challengectl.db'):
        return 'challengectl.db'
    else:
        logger.error("Could not find database file. Run this script from the project root or server directory.")
        sys.exit(1)


def generate_thumbnail(image_path, recording_id):
    """
    Generate a 300x300 square thumbnail with top-aligned cropping.

    Args:
        image_path: Path to the full-resolution image
        recording_id: Recording ID for naming the thumbnail

    Returns:
        Path to the generated thumbnail, or None if generation failed
    """
    try:
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return None

        # Determine thumbnail path
        image_dir = os.path.dirname(image_path)
        thumbnail_filename = f"recording_{recording_id}_thumb.png"
        thumbnail_path = os.path.join(image_dir, thumbnail_filename)

        # Skip if thumbnail already exists
        if os.path.exists(thumbnail_path):
            logger.info(f"Thumbnail already exists for recording {recording_id}, skipping")
            return thumbnail_path

        # Open and process image
        with Image.open(image_path) as img:
            width, height = img.size
            thumbnail_size = 300

            # Calculate crop box for top-aligned square crop
            if width >= height:
                # Image is wider than tall, crop from left edge
                crop_box = (0, 0, height, height)
            else:
                # Image is taller than wide, crop from top
                crop_box = (0, 0, width, width)

            # Crop and resize to thumbnail
            thumbnail = img.crop(crop_box)
            thumbnail = thumbnail.resize((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)

            # Save thumbnail with optimized PNG
            thumbnail.save(thumbnail_path, 'PNG', optimize=True)

            logger.info(f"Generated thumbnail for recording {recording_id}: {thumbnail_size}x{thumbnail_size}px")
            return thumbnail_path

    except Exception as e:
        logger.error(f"Failed to generate thumbnail for recording {recording_id}: {e}")
        return None


def main():
    """Main migration function."""
    logger.info("Starting thumbnail generation for existing recordings")

    # Get database path
    db_path = get_database_path()
    logger.info(f"Using database: {db_path}")

    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Find recordings with images but no thumbnails
        cursor.execute('''
            SELECT recording_id, image_path, thumbnail_path
            FROM recordings
            WHERE image_path IS NOT NULL
            AND (thumbnail_path IS NULL OR thumbnail_path = '')
            AND status = 'completed'
        ''')

        recordings = cursor.fetchall()
        total = len(recordings)

        if total == 0:
            logger.info("No recordings need thumbnail generation")
            return

        logger.info(f"Found {total} recordings that need thumbnails")

        # Process each recording
        success_count = 0
        skip_count = 0
        error_count = 0

        for recording in recordings:
            recording_id = recording['recording_id']
            image_path = recording['image_path']

            logger.info(f"Processing recording {recording_id} ({success_count + skip_count + error_count + 1}/{total})")

            # Generate thumbnail
            thumbnail_path = generate_thumbnail(image_path, recording_id)

            if thumbnail_path:
                # Check if this was a skip (thumbnail already existed)
                if recording['thumbnail_path']:
                    skip_count += 1
                else:
                    # Update database
                    cursor.execute('''
                        UPDATE recordings
                        SET thumbnail_path = ?
                        WHERE recording_id = ?
                    ''', (thumbnail_path, recording_id))
                    conn.commit()
                    success_count += 1
            else:
                error_count += 1

        logger.info(f"Thumbnail generation complete:")
        logger.info(f"  - Success: {success_count}")
        logger.info(f"  - Skipped: {skip_count}")
        logger.info(f"  - Errors: {error_count}")

        conn.close()

    except Exception as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
