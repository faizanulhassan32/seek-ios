import requests
from utils.logger import setup_logger

logger = setup_logger('image_utils')

def validate_image_url(url: str) -> bool:
    """
    Validate that an image URL returns a valid image.

    Args:
        url: Image URL to validate

    Returns:
        True if URL returns 200 status with image/* content-type, False otherwise
    """
    if not url:
        return False
        
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)

        # Check status code
        if response.status_code != 200:
            logger.debug(f"Image validation failed: status {response.status_code} for {url}")
            return False

        # Check Content-Type header
        content_type = response.headers.get('Content-Type', '').lower()
        if not content_type.startswith('image/'):
            logger.debug(f"Image validation failed: Content-Type '{content_type}' for {url}")
            return False

        logger.debug(f"Image validated successfully: {url}")
        return True

    except requests.RequestException as e:
        logger.debug(f"Image validation failed: {type(e).__name__} for {url}")
        return False
    except Exception as e:
        logger.debug(f"Image validation unexpected error: {str(e)} for {url}")
        return False
