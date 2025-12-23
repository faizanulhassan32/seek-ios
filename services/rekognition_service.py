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
            # Validate input data
            if not data or len(data) == 0:
                logger.warning("Empty image data provided")
                return None
            
            with Image.open(io.BytesIO(data)) as img:
                # Verify image is valid
                img.verify()
            
            # Reopen after verify (verify closes the file)
            with Image.open(io.BytesIO(data)) as img:
                # Skip corrupted or invalid images
                if img.size[0] == 0 or img.size[1] == 0:
                    logger.warning("Image has zero dimensions")
                    return None
                
                # Convert to RGB (strip alpha) for JPEG compatibility
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Encode as JPEG to ensure compatibility
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=90, optimize=True)
                normalized = buf.getvalue()
                
                # Final validation: ensure we have valid JPEG data
                if len(normalized) == 0:
                    logger.warning("Normalized image is empty")
                    return None

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

    def validate_candidate_image(self, image_url: str) -> bool:
        """
        Validate that a candidate image is usable for face comparison.
        
        Checks:
        1. Image can be downloaded
        2. Content-Type is image/*
        3. Image contains at least one face
        
        Args:
            image_url: URL of the candidate image
            
        Returns:
            True if image passes all validation checks, False otherwise
        """
        if not self.client:
            logger.warning("Rekognition client not initialized, skipping validation")
            return False
        
        if not image_url:
            return False
        
        try:
            # Step 1: Try to download the image
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            }
            resp = requests.get(image_url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            
            # Step 2: Check Content-Type
            content_type = resp.headers.get('Content-Type', '').lower()
            if not content_type.startswith('image/'):
                logger.debug(f"{image_url} > Invalid content-type '{content_type}'")
                return False
            
            image_bytes = resp.content
            if not image_bytes or len(image_bytes) == 0:
                logger.debug(f"{image_url} > Empty image data")
                return False
            
            # Step 3: Normalize and check if valid image
            normalized = self._normalize_image_bytes(image_bytes)
            if not normalized:
                logger.debug(f"{image_url} > Image normalization failed")
                return False
            
            # Step 4: Detect faces
            response = self.client.detect_faces(
                Image={'Bytes': normalized},
                Attributes=['DEFAULT']
            )
            
            faces = response.get('FaceDetails', [])
            if len(faces) == 0:
                logger.debug(f"{image_url} > No face detected")
                return False
            
            logger.debug(f"{image_url} > ✅ Validated ({len(faces)} face(s) detected)")
            return True
            
        except Exception as e:
            logger.debug(f"{image_url} > Validation failed: {e}")
            return False

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
                logger.debug(f"{image_url} > Face detected ({len(faces)} face(s))")
            else:
                logger.debug(f"{image_url} > No face detected")
                
            return has_face
            
        except Exception as e:
            logger.warning(f"{image_url} > Face detection failed: {e}")
            return False  # Exclude images that fail detection


_rekognition_service = None


def get_rekognition_service() -> RekognitionService:
    global _rekognition_service
    if _rekognition_service is None:
        _rekognition_service = RekognitionService()
    return _rekognition_service
