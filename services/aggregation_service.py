from typing import Dict, List
from utils.logger import setup_logger
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.image_proxy_service import get_image_proxy_service

logger = setup_logger('aggregation_service')

class AggregationService:
    """Service for aggregating and normalizing data from multiple sources"""

    def __init__(self):
        self.image_proxy = get_image_proxy_service()

    def aggregate_person_data(
        self,
        query: str,
        websearch_result: Dict,
        apify_results: List[Dict],
        structured_info: Dict,
        pdl_data: Dict = None
    ) -> Dict:
        """
        Aggregate data from all sources into a unified Person schema
        """
        logger.info(f"Aggregating person data for query: {query}")

        # Start with structured info from websearch
        basic_info = structured_info.get('basic_info', {})
        social_profiles = structured_info.get('social_profiles', [])
        photos = structured_info.get('photos', [])
        notable_mentions = structured_info.get('notable_mentions', [])
        
        # Build raw_sources list (initially from structured info or empty)
        # Note: raw_sources is built later in the code, but we want to append PDL source too
        # We'll just ensure we have access to it or append it to a list we use later.
        # Actually, raw_sources is initialized at the end of the method.
        # Let's add PDL extraction logic here.

        # Integrate PDL Data
        if pdl_data:
            # Basic Info
            pdl_basic = {
                'name': pdl_data.get('full_name'),
                'occupation': pdl_data.get('job_title'),
                'location': pdl_data.get('location_name'),
                'company': pdl_data.get('job_company_name'),
                'education': [
                    edu.get('school', {}).get('name') 
                    for edu in pdl_data.get('education', []) 
                    if edu.get('school', {}).get('name')
                ]
            }
            basic_info = self._merge_basic_info(basic_info, pdl_basic)
            
            # Social Profiles from PDL
            if pdl_data.get('linkedin_url'):
                social_profiles.append({
                    'platform': 'linkedin',
                    'username': pdl_data.get('linkedin_username'),
                    'url': pdl_data.get('linkedin_url'),
                    'source': 'pdl'
                })
            if pdl_data.get('twitter_url'):
                social_profiles.append({
                    'platform': 'twitter',
                    'username': pdl_data.get('twitter_username'),
                    'url': pdl_data.get('twitter_url'),
                    'source': 'pdl'
                })
            if pdl_data.get('facebook_url'):
                 social_profiles.append({
                    'platform': 'facebook',
                    'username': pdl_data.get('facebook_username'),
                    'url': pdl_data.get('facebook_url'),
                    'source': 'pdl'
                })

        # Add social profiles from Apify results
        for result in apify_results:
            if not result.get('success', False):
                continue

            source = result.get('source', '')
            data = result.get('data', {})

            if source == 'instagram':
                social_profiles.append(self._extract_instagram_profile(data))
                photos.extend(self._extract_instagram_photos(data))

            elif source == 'twitter':
                social_profiles.append(self._extract_twitter_profile(data))
                photos.extend(self._extract_twitter_photos(data))

            elif source == 'linkedin':
                social_profiles.append(self._extract_linkedin_profile(data))
                # Enhance basic_info with LinkedIn data
                basic_info = self._merge_basic_info(basic_info, self._extract_linkedin_basic_info(data))

        # Deduplicate social profiles and photos
        social_profiles = self._deduplicate_list(social_profiles, key='platform')
        photos = self._deduplicate_list(photos, key='url')

        # --- PROXY IMAGES ---
        # Collect all URLs that need proxying
        urls_to_proxy = []
        
        # 1. Photo URLs
        for photo in photos:
            if photo.get('url'):
                urls_to_proxy.append(photo['url'])
                
        # 2. Profile Pic URLs
        for profile in social_profiles:
            if profile.get('profile_pic'):
                urls_to_proxy.append(profile['profile_pic'])
                
        # Proxy them in parallel
        if urls_to_proxy:
            logger.info(f"Proxying {len(urls_to_proxy)} images...")
            proxy_map = self._proxy_images_parallel(urls_to_proxy)
            logger.info(f"Successfully proxied {len(proxy_map)}/{len(set(urls_to_proxy))} unique images")

            # Replace URLs in photos and filter out failed proxies
            successful_photos = []
            failed_count = 0
            
            for photo in photos:
                original_url = photo.get('url')
                if original_url and original_url in proxy_map:
                    photo['url'] = proxy_map[original_url]
                    successful_photos.append(photo)
                elif original_url:
                    # Proxy failed or didn't return a result, but we keep the original URL
                    # This is important for "candidate_selection" images which we know are likely valid
                    # even if our backend couldn't reach them (e.g. 403 to servers but not clients)
                    successful_photos.append(photo)
                    logger.debug(f"Proxy failed for {original_url}, keeping original")
                else:
                    # No URL at all
                    failed_count += 1

            if failed_count > 0:
                logger.info(f"Filtered out {failed_count} photos with empty URLs")

            photos = successful_photos

            # Replace URLs in social profiles (keep profiles even if pic fails)
            for profile in social_profiles:
                original_url = profile.get('profile_pic')
                if original_url and original_url in proxy_map:
                    profile['profile_pic'] = proxy_map[original_url]
                elif original_url:
                    # Profile pic failed - remove it but keep the profile
                    profile['profile_pic'] = None
                    logger.debug(f"Removed failed profile pic for user: {profile.get('username')}")
        # --------------------

        # Build raw_sources for transparency
        # Build raw_sources for transparency
        raw_sources = []
        # OpenAI websearch source hidden per user request


        for result in apify_results:
            if result.get('success', False):
                raw_sources.append({
                    'source': result.get('source'),
                    'timestamp': None,
                    'summary': f"Scraped {result.get('source')} data"
                })

        if pdl_data:
            # Skip adding PDL to raw sources as per user request to hide it from UI
            pass
            # raw_sources.append({
            #     'source': 'people_data_labs',
            #     'timestamp': None,
            #     'summary': 'Enriched profile data from People Data Labs'
            # })

        # OSINT Data Processing
        public_records = {'relatives': [], 'locations': []}
        
        for result in apify_results:
            source = result.get('source', '')
            data = result.get('data', {})
            
            if source in ['truepeoplesearch', 'familytreenow', 'peekyou', 'idcrawl']:
                 # Extract public records from these sources
                 records = self._extract_public_records(data)
                 if records.get('relatives'):
                     public_records['relatives'].extend(records['relatives'])
                     
                 # Allow locations if we don't have them yet or just collect them
                 # For now, we store them in public_records, separate from main basic_info location
                 if records.get('locations'):
                     public_records['locations'].extend(records['locations'])

        # Deduplicate public records
        public_records['relatives'] = list(set(public_records['relatives']))
        public_records['locations'] = list(set(public_records['locations']))

        aggregated_data = {
            'query': query,
            'basic_info': basic_info,
            'social_profiles': social_profiles,
            'photos': photos,
            'notable_mentions': notable_mentions,
            'public_records': public_records,  # New field
            'raw_sources': raw_sources
        }

        logger.info(f"Aggregation complete. Found {len(social_profiles)} social profiles, {len(photos)} photos")

        return aggregated_data

    def _proxy_images_parallel(self, urls: List[str]) -> Dict[str, str]:
        """
        Proxy a list of image URLs in parallel.
        Returns a map of {original_url: proxied_url}
        """
        proxy_map = {}
        # Deduplicate input URLs to avoid redundant work
        unique_urls = list(set(urls))
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(self.image_proxy.proxy_image, url): url 
                for url in unique_urls
            }
            
            for future in as_completed(future_to_url):
                original_url = future_to_url[future]
                try:
                    proxied_url = future.result()
                    if proxied_url:
                        proxy_map[original_url] = proxied_url
                except Exception as e:
                    logger.error(f"Error proxying image {original_url}: {e}")
                    
        return proxy_map

    def _extract_instagram_profile(self, data: Dict) -> Dict:
        """Extract Instagram profile information"""
        if not data:
            return {}

        return {
            'platform': 'instagram',
            'username': data.get('username', ''),
            'url': f"https://instagram.com/{data.get('username', '')}",
            'full_name': data.get('fullName', ''),
            'bio': data.get('biography', ''),
            'followers': data.get('followersCount', 0),
            'following': data.get('followsCount', 0),
            'posts': data.get('postsCount', 0),
            'verified': data.get('verified', False),
            'profile_pic': data.get('profilePicUrl', '')
        }

    def _extract_instagram_photos(self, data: Dict) -> List[Dict]:
        """Extract photos from Instagram data"""
        photos = []
        posts = data.get('latestPosts', []) if data else []

        for post in posts[:10]:  # Limit to 10 photos
            if post.get('displayUrl'):
                photos.append({
                    'url': post.get('displayUrl'),
                    'source': 'instagram',
                    'caption': post.get('caption', '')[:200],
                    'likes': post.get('likesCount', 0)
                })

        return photos

    def _extract_twitter_profile(self, data: List[Dict]) -> Dict:
        """Extract Twitter profile information"""
        if not data or len(data) == 0:
            return {}

        # Get user info from first tweet
        first_tweet = data[0]
        user = first_tweet.get('user', {})

        return {
            'platform': 'twitter',
            'username': user.get('screen_name', ''),
            'url': f"https://twitter.com/{user.get('screen_name', '')}",
            'full_name': user.get('name', ''),
            'bio': user.get('description', ''),
            'followers': user.get('followers_count', 0),
            'following': user.get('friends_count', 0),
            'posts': user.get('statuses_count', 0),
            'verified': user.get('verified', False),
            'profile_pic': user.get('profile_image_url_https', '')
        }

    def _extract_twitter_photos(self, data: List[Dict]) -> List[Dict]:
        """Extract photos from Twitter data"""
        photos = []

        for tweet in data[:10]:  # Limit to 10 photos
            media = tweet.get('entities', {}).get('media', [])
            for m in media:
                if m.get('type') == 'photo' and m.get('media_url_https'):
                    photos.append({
                        'url': m.get('media_url_https'),
                        'source': 'twitter',
                        'caption': tweet.get('full_text', '')[:200],
                        'likes': tweet.get('favorite_count', 0)
                    })

        return photos

    def _extract_linkedin_profile(self, data: Dict) -> Dict:
        """Extract LinkedIn profile information"""
        if not data:
            return {}

        return {
            'platform': 'linkedin',
            'username': data.get('publicIdentifier', ''),
            'url': data.get('url', ''),
            'full_name': f"{data.get('firstName', '')} {data.get('lastName', '')}".strip(),
            'headline': data.get('headline', ''),
            'location': data.get('location', ''),
            'connections': data.get('connectionsCount', 0),
            'profile_pic': data.get('profilePicture', '')
        }

    def _extract_linkedin_basic_info(self, data: Dict) -> Dict:
        """Extract basic info from LinkedIn data"""
        if not data:
            return {}

        return {
            'name': f"{data.get('firstName', '')} {data.get('lastName', '')}".strip(),
            'occupation': data.get('headline', ''),
            'location': data.get('location', ''),
            'education': [edu.get('schoolName', '') for edu in data.get('education', [])],
            'company': data.get('experience', [{}])[0].get('companyName', '') if data.get('experience') else ''
        }

    def _merge_basic_info(self, info1: Dict, info2: Dict) -> Dict:
        """Merge two basic_info dictionaries, preferring non-empty values"""
        merged = info1.copy()

        for key, value in info2.items():
            if value and (key not in merged or not merged[key]):
                merged[key] = value

        return merged
    def _extract_public_records(self, data: Dict) -> Dict:
        """
        Extract relatives and locations from raw OSINT text 
        (Uses LLM for robustness, falls back to Regex)
        """
        text = data.get('text_content', '')
        if not text:
            return {}
            
        # Try LLM Extraction first
        try:
            from services.answer_service import get_answer_service
            answer_service = get_answer_service()
            llm_records = answer_service.extract_osint_data(text)
            
            if llm_records.get('relatives') or llm_records.get('locations'):
                logger.info("Successfully extracted OSINT data via LLM")
                return llm_records
        except Exception as e:
            logger.warning(f"LLM OSINT extraction failed, falling back to regex: {e}")

        # Fallback: Regex Extraction
        records = {'relatives': [], 'locations': []}
        
        # 1. Extract Relatives
        relatives_pattern = re.search(r'(?:Possible Matches|Possible Relatives|Related To|Associates)(?:[:\s]+)(.*?)(?:Born|Age|Lives|Associates|Properties|$)', text, re.IGNORECASE | re.DOTALL)
        
        if relatives_pattern:
            raw_relatives = relatives_pattern.group(1)
            candidates = [r.strip() for r in re.split(r'[,|\n]', raw_relatives) if len(r.strip()) > 3 and len(r.strip()) < 30]
            valid_relatives = [c for c in candidates if re.match(r'^[A-Z][a-z]+(\s[A-Z][a-z]+)+$', c)]
            records['relatives'] = valid_relatives[:10]
            
        # 2. Extract Locations
        lives_in_pattern = re.search(r'(?:Lives In|Resides In|Address)(?:[:\s]+)(.*?)(?:Born|Age|Related|Associates|$)', text, re.IGNORECASE | re.DOTALL)
        
        if lives_in_pattern:
             raw_loc = lives_in_pattern.group(1)
             loc_matches = re.findall(r'([A-Z][a-zA-Z\s]+,\s[A-Z]{2})', raw_loc)
             records['locations'] = list(set(loc_matches))[:5]
             
        return records
    def _deduplicate_list(self, items: List[Dict], key: str) -> List[Dict]:
        """Deduplicate a list of dictionaries based on a key"""
        seen = set()
        unique_items = []

        for item in items:
            if not item:
                continue

            identifier = item.get(key)
            
            # Special handling for URLs: strip query parameters for deduplication
            if key == 'url' and identifier and isinstance(identifier, str):
                # Split by '?' and take the first part
                identifier = identifier.split('?')[0]

            if identifier and identifier not in seen:
                seen.add(identifier)
                unique_items.append(item)

        return unique_items


# Singleton instance
_aggregation_service = None

def get_aggregation_service() -> AggregationService:
    """Get or create the AggregationService singleton"""
    global _aggregation_service
    if _aggregation_service is None:
        _aggregation_service = AggregationService()
    return _aggregation_service
