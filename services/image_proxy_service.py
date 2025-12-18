import requests
import hashlib
import os
import time
from typing import Optional
from urllib.parse import urlparse
from db.supabase_client import get_supabase_client
from utils.logger import setup_logger

logger = setup_logger('image_proxy_service')

class ImageProxyService:
    """
    Service to proxy external images through Supabase Storage.
    This solves issues with:
    1. Image expiration (hotlinks dying)
    2. CORS/Referer blocking (e.g. from Instagram/Twitter)
    3. Mixed content warnings
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.bucket_name = "person_images"
        
    def proxy_image(self, url: str) -> Optional[str]:
        """
        Downloads an image from a URL, caches it in Supabase, and returns the public URL.
        Returns None if the image cannot be processed.
        """
        if not url:
            return None
            
        # 1. Generate a unique filename based on the URL
        # We use a hash so we can deterministically find it again without re-downloading
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        
        # Try to keep the original extension, default to .jpg
        path = urlparse(url).path
        ext = os.path.splitext(path)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            ext = '.jpg'
            
        filename = f"{url_hash}{ext}"
        storage_path = f"cache/{filename}"
        
        # 2. Check if it already exists in Supabase (Cache Hit)
        # Note: file_exists might be slow if we have millions of files. 
        # For now, we can rely on the fact that 'get_public_url' is deterministic.
        # But to avoid re-downloading/re-uploading, we should check.
        if self.supabase.file_exists(self.bucket_name, storage_path):
            logger.debug(f"Cache hit for image: {url}")
            return self.supabase.get_public_url(self.bucket_name, storage_path)
            
        # 3. Cache Miss - Download the image with retry logic
        logger.debug(f"Cache miss. Downloading image: {url}")

        # Use headers to mimic a browser to avoid blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }

        # Retry logic with exponential backoff
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 200:
                    # Success! Validate content
                    content_type = response.headers.get('Content-Type', '').lower()
                    content_length = response.headers.get('Content-Length')
                    
                    # 1. Validate Content-Type
                    if not content_type.startswith('image/'):
                        logger.warning(f"Invalid content type for {url}: {content_type}")
                        return None
                        
                    # 2. Validate Content-Length (if present)
                    # Skip images smaller than 1KB (likely tracking pixels or broken icons)
                    if content_length and int(content_length) < 1024:
                        logger.warning(f"Image too small ({content_length} bytes): {url}")
                        return None
                        
                    # 3. Validate actual content size
                    if len(response.content) < 1024:
                        logger.warning(f"Image content too small ({len(response.content)} bytes): {url}")
                        return None

                    try:
                        upload_result = self.supabase.upload_file(
                            bucket=self.bucket_name,
                            path=storage_path,
                            file_data=response.content,
                            content_type=content_type
                        )
                        
                        # Check if upload actually succeeded
                        if upload_result is None:
                            logger.error(f"Upload failed for {url}: upload_file returned None")
                            return None
                            
                        return self.supabase.get_public_url(self.bucket_name, storage_path)
                    except Exception as upload_error:
                        logger.error(f"Error uploading file to Supabase for {url}: {str(upload_error)}")
                        return None

                elif response.status_code == 429:
                    # Rate limited - retry with backoff
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 0.5  # 0.5s, 1.0s, 2.0s
                        logger.debug(f"Rate limited (429), retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"Failed to download image {url}: Status 429 after {max_retries} retries")
                        return None

                elif response.status_code in [403, 404]:
                    # Don't retry for forbidden or not found
                    logger.warning(f"Failed to download image {url}: Status {response.status_code} (not retrying)")
                    return None

                else:
                    # Other error - retry once
                    if attempt < max_retries - 1:
                        logger.debug(f"Download failed with status {response.status_code}, retrying (attempt {attempt + 1}/{max_retries})")
                        time.sleep(0.5)
                        continue
                    else:
                        logger.warning(f"Failed to download image {url}: Status {response.status_code}")
                        return None

            except requests.Timeout:
                if attempt < max_retries - 1:
                    logger.debug(f"Request timeout, retrying (attempt {attempt + 1}/{max_retries})")
                    time.sleep(0.5)
                    continue
                else:
                    logger.warning(f"Failed to download image {url}: Timeout after {max_retries} retries")
                    return None

            except Exception as e:
                logger.error(f"Error proxying image {url}: {str(e)}")
                return None

        return None

# Singleton instance
_image_proxy_service = None

def get_image_proxy_service() -> ImageProxyService:
    """Get or create the ImageProxyService singleton"""
    global _image_proxy_service
    if _image_proxy_service is None:
        _image_proxy_service = ImageProxyService()
    return _image_proxy_service
