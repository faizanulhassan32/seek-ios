"""
Reference Photo Cleanup Scheduler
Runs a periodic job every 60 minutes to clear ALL reference photos from Supabase Storage.
This ensures the bucket is completely emptied regularly.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from db.supabase_client import get_supabase_client
from utils.logger import setup_logger

logger = setup_logger('cleanup_scheduler')

# Configuration
REFERENCE_PHOTOS_BUCKET = 'reference-photos'
CLEANUP_INTERVAL_MINUTES = 60  # Run cleanup every 60 minutes


def cleanup_expired_reference_photos():
    """
    Delete ALL reference photos from Supabase Storage bucket.
    Runs every 60 minutes to completely clear the bucket.
    """
    try:
        logger.info("Starting reference photo cleanup job (clearing entire bucket)...")
        
        supabase = get_supabase_client()
        
        # List all files in the reference-photos bucket (root path)
        response = supabase.client.storage.from_(REFERENCE_PHOTOS_BUCKET).list(path='')
        logger.info(response)

        if not response:
            logger.info("No reference photos found in bucket")
            return

        # Collect all file names
        file_names = [file.get('name') for file in response if isinstance(file, dict)]
        
        if not file_names:
            logger.info("No files to delete")
            return
        
        # Delete all files in one batch
        supabase.client.storage.from_(REFERENCE_PHOTOS_BUCKET).remove(file_names)
        
        logger.info(f"Cleanup job completed. Deleted all {len(file_names)} reference photos from bucket")
        
    except Exception as e:
        logger.error(f"Reference photo cleanup job failed: {e}")


def start_cleanup_scheduler():
    """
    Initialize and start the background scheduler for reference photo cleanup.
    Clears entire bucket every 60 minutes.
    """
    scheduler = BackgroundScheduler()
    
    # Schedule cleanup job to run every 60 minutes (clears entire bucket)
    scheduler.add_job(
        func=cleanup_expired_reference_photos,
        trigger='interval',
        minutes=CLEANUP_INTERVAL_MINUTES,
        id='cleanup_reference_photos',
        name='Clear all reference photos from bucket',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Reference photo cleanup scheduler started. Clearing entire bucket every {CLEANUP_INTERVAL_MINUTES} minutes")
    
    return scheduler

