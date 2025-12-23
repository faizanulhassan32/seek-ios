import os
import requests
import re
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger('serpapi_service')

class SerpApiService:
    """Service for fetching data from SerpApi"""
    
    BASE_URL = "https://serpapi.com/search"
    
    def __init__(self):
        self.api_key = os.getenv('SERPAPI_KEY')
        if not self.api_key:
            logger.warning("SERPAPI_KEY not set in environment variables")
            
    def fetch_candidates(self, query: str) -> List[Dict]:
        """
        Fetch potential candidates from SerpApi (Google Search)
        
        Args:
            query: The search query
            
        Returns:
            List of candidate dictionaries with id, name, description, imageUrl
        """
        if not self.api_key:
            logger.error("Cannot fetch candidates: SERPAPI_KEY missing")
            return []
            
        try:
            pages_to_scroll=4
            base_params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "google_domain": "google.com",
                "gl": "us",
                "hl": "en",
                "num": pages_to_scroll
            }
            
            logger.info(f"Fetching candidates from SerpApi for: {query} ({pages_to_scroll}) pages)")
            
            raw_candidates = []
            for page in range(pages_to_scroll):

                params = {**base_params, "start": page * pages_to_scroll}
                
                try:
                    response = requests.get(self.BASE_URL, params=params)
                    response.raise_for_status()
                    data = response.json()
                                        
                    # 1. Check Knowledge Graph (High confidence) - first page only
                    if page == 0 and "knowledge_graph" in data:
                        kg = data["knowledge_graph"]
                        candidate = self._parse_knowledge_graph(kg)
                        if candidate:
                            raw_candidates.append(candidate)
                            
                    # 2. Check Organic Results (accept all, no domain filtering)
                    for result in data.get("organic_results", []):
                        candidate = self._parse_organic_result(result)
                        if candidate:
                            raw_candidates.append(candidate)
                    
                    # 3. Check Related Searches - first page only
                    if page == 0 and "related_searches" in data:
                        for related in data["related_searches"]:
                            candidate = self._parse_related_search(related)
                            if candidate:
                                raw_candidates.append(candidate)
                                
                except Exception as page_err:
                    logger.warning(f"Page {page+1} error: {page_err}")

            # Deduplication Logic
            unique_candidates = []
            seen_keys = set()
            seen_image_urls = set()
            
            for cand in raw_candidates:
                # Create dedup key from name + first 80 chars of description
                name_key = cand['id'].lower().strip()
                desc_key = cand.get('description', '')[:80].lower().strip()
                key = f"{name_key}::{desc_key}"
                
                # Check if this image URL has already been used
                img_url = cand.get('imageUrl')
                
                # Skip if duplicate key OR duplicate image URL
                if key in seen_keys:
                    continue
                if img_url and img_url in seen_image_urls:
                    continue
                
                # Add to results
                unique_candidates.append(cand)
                seen_keys.add(key)
                if img_url:
                    seen_image_urls.add(img_url)
            
            # Convert back to list and limit
            candidates = unique_candidates
            return candidates
            
        except Exception as e:
            logger.error(f"Error fetching from SerpApi: {str(e)}", exc_info=True)
            return []

    def fetch_image_url(self, query: str) -> Optional[str]:
        """
        Fetch the first image URL for a query using Google Images via SerpApi
        """
        if not self.api_key:
            return None
            
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google_images",
                "google_domain": "google.com",
                "gl": "us",
                "hl": "en",
                "num": 1
            }
            
            response = requests.get(self.BASE_URL, params=params)
            if response.status_code == 200:
                data = response.json()
                if "images_results" in data and data["images_results"]:
                    return data["images_results"][0].get("original") or data["images_results"][0].get("thumbnail")
            
            return None
        except Exception as e:
            logger.error(f"Error fetching image from SerpApi: {str(e)}")
            return None

    def fetch_multiple_images(self, query: str, count: int = 5) -> List[str]:
        """
        Fetch multiple image URLs for a query using Google Images via SerpApi
        """
        if not self.api_key:
            return []
            
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google_images",
                "google_domain": "google.com",
                "gl": "us",
                "hl": "en",
                "num": count
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                images = []
                for result in data.get("images_results", [])[:count]:
                    img_url = result.get("original")
                    if img_url:
                        images.append(img_url)
                
                logger.info(f"Found {len(images)} images for query: {query}")
                return images
            
            return []
        except Exception as e:
            logger.error(f"Error fetching multiple images from SerpApi: {str(e)}")
            return []

    def _parse_knowledge_graph(self, kg: Dict) -> Optional[Dict]:
        """Parse a Knowledge Graph entry into a candidate dict"""
        try:
            name = kg.get("title")
            if not name:
                return None
                
            description = kg.get("description") or kg.get("type")
            
            # Image
            image_url = None
            if "header_images" in kg and kg["header_images"]:
                image_url = kg["header_images"][0].get("image")
            elif "images" in kg and kg["images"]:
                image_url = kg["images"][0]
                
            return {
                "id": name,
                "name": name,
                "description": description,
                "imageUrl": image_url
            }
        except Exception as e:
            logger.error(f"Error parsing KG: {str(e)}")
            return None

    def _clean_name(self, name: str) -> str:
        """Clean name by removing common suffixes and extra info"""
        if not name:
            return ""
        # Remove content in parentheses, e.g. "Elon Musk (Entrepreneur)" -> "Elon Musk"
        name = re.sub(r'\s*\(.*?\)', '', name)
        # Remove platform suffixes, e.g. "Elon Musk | LinkedIn" -> "Elon Musk"
        name = re.split(r'\s+[|\-]\s+', name)[0]
        # Remove "on [Platform]" suffix
        name = re.sub(r'\s+on\s+(Instagram|Twitter|LinkedIn|Facebook).*$', '', name, flags=re.IGNORECASE)
        # Remove numeric prefixes like "20+ " or "10 " often found in listicles
        name = re.sub(r'^\d+\+?\s+', '', name)
        # Remove "Top X " prefixes
        name = re.sub(r'^Top\s+\d+\s+', '', name, flags=re.IGNORECASE)
        return name.strip()

    def _parse_organic_result(self, result: Dict) -> Optional[Dict]:
        """Parse an organic result into a candidate dict"""
        try:
            title = result.get("title", "")
            if not title:
                return None
                
            # Clean title using heuristic method
            name = self._clean_name(title)
            if not name:
                return None
            
            snippet = result.get("snippet", "")
            
            # Image (thumbnail)
            image_url = result.get("thumbnail")
            
            return {
                "id": name,
                "name": name,
                "description": snippet,
                "imageUrl": image_url
            }
        except Exception as e:
            # Don't log every organic parse error to avoid noise
            return None

    def _parse_related_search(self, related: Dict) -> Optional[Dict]:
        """Parse a related search entry"""
        try:
            query = related.get("query")
            if not query:
                return None
                
            # Only include if it looks like a person's name (heuristic: usually short, no "vs", "net worth", etc.)
            # This is a weak heuristic, but better than nothing.
            # Actually, related searches often have 'thumbnail' if they are entities.
            image_url = related.get("thumbnail")
            
            # If no image, it might just be a keyword search. 
            # But for "candidates", we prefer things that look like entities.
            # Let's include it if it has an image OR if we are desperate (but we have organic results).
            # Let's restrict to having an image for higher quality.
            if not image_url:
                return None
                
            return {
                "id": query,
                "name": query,
                "description": "Related search", # Generic description
                "imageUrl": image_url
            }
        except Exception as e:
            return None

# Singleton
_serpapi_service = None

def get_serpapi_service() -> SerpApiService:
    global _serpapi_service
    if _serpapi_service is None:
        _serpapi_service = SerpApiService()
    return _serpapi_service
