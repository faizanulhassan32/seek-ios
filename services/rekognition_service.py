import os
import io
import requests
from typing import Optional
from utils.logger import setup_logger
import boto3
from PIL import Image

logger = setup_logger('rekognition_service')

class RekognitionService:
    """Thin wrapper around AWS Rekognition compare_faces."""

    def __init__(self):
        if boto3 is None:
            self.client = None
            return
        try:
            self.client = boto3.client(
                'rekognition',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION'),
            )
        except Exception as e:
            logger.warning(f"Failed to init Rekognition client: {e}")
            self.client = None

    def _normalize_image_bytes(self, data: bytes) -> Optional[bytes]:
        """Convert arbitrary image bytes to a Rekognition-supported format (JPEG/PNG) and size.
        Returns normalized bytes or None if not convertible.
        """
        try:
            with Image.open(io.BytesIO(data)) as img:
                # Convert to RGB (strip alpha) for JPEG compatibility
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Resize if too large (> 4096 px on either side)
                max_side = max(img.size)
                if max_side > 4096:
                    scale = 4096 / float(max_side)
                    new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
                    img = img.resize(new_size)

                # Encode as JPEG to ensure compatibility and reduce size
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=90, optimize=True)
                normalized = buf.getvalue()

                # If still very large (> 5MB), downscale further
                if len(normalized) > 5 * 1024 * 1024:
                    img = img.resize((int(img.size[0] * 0.75), int(img.size[1] * 0.75)))
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85, optimize=True)
                    normalized = buf.getvalue()

                return normalized
        except Exception as e:
            logger.warning(f"Failed to normalize image: {e}")
        return None

    def _download_image(self, url: str) -> Optional[bytes]:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            }
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.warning(f"Failed to download image from {url}: {e}")
            return None

    def compare_faces_bytes(self, source_bytes: bytes, target_url: str) -> Optional[float]:
        """Compare a reference image (bytes) to a target image (URL). Returns similarity score or 0."""
        if not self.client:
            return 0.0
        if not target_url:
            return 0.0
        try:
            # Normalize both source and target images to JPEG
            norm_source = self._normalize_image_bytes(source_bytes)
            if not norm_source:
                logger.warning("Source image could not be normalized for Rekognition")
                return 0.0

            raw_target = self._download_image(target_url)
            if not raw_target:
                return 0.0
            norm_target = self._normalize_image_bytes(raw_target)
            if not norm_target:
                logger.warning("Target image could not be normalized for Rekognition")
                return 0.0

            response = self.client.compare_faces(
                SourceImage={'Bytes': norm_source},
                TargetImage={'Bytes': norm_target},
                SimilarityThreshold=70,
            )
            matches = response.get('FaceMatches') or []
            if not matches:
                return 0.0
            best = max(m.get('Similarity', 0.0) for m in matches)
            return float(best)
        except Exception as e:
            logger.warning(f"Rekognition compare_faces failed: {e}")
            return 0.0

    def detect_faces_in_url(self, image_url: str) -> bool:
        """
        Check if an image contains at least one face.
        
        Args:
            image_url: URL of the image to check
            
        Returns:
            True if at least one face is detected, False otherwise
        """
        if not self.client:
            logger.warning("Rekognition client not initialized, skipping face detection")
            return True  # Default to True if service unavailable
            
        try:
            # Download and normalize image
            raw_image = self._download_image(image_url)
            if not raw_image:
                return False
                
            norm_image = self._normalize_image_bytes(raw_image)
            if not norm_image:
                return False
            
            # Detect faces
            response = self.client.detect_faces(
                Image={'Bytes': norm_image},
                Attributes=['DEFAULT']
            )
            
            faces = response.get('FaceDetails', [])
            has_face = len(faces) > 0
            
            if has_face:
                logger.debug(f"Face detected in image: {image_url}")
            else:
                logger.debug(f"No face detected in image: {image_url}")
                
            return has_face
            
        except Exception as e:
            logger.warning(f"Face detection failed for {image_url}: {e}")
            return False  # Exclude images that fail detection


_rekognition_service = None


def get_rekognition_service() -> RekognitionService:
    global _rekognition_service
    if _rekognition_service is None:
        _rekognition_service = RekognitionService()
    return _rekognition_service
