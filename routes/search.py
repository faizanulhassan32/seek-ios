from flask import Blueprint, request, jsonify
from typing import Dict, List, Optional
import os
import requests
import base64
import tempfile
import json
from datetime import datetime as dt
from services.websearch_service import get_websearch_service
from services.apify_service import get_apify_service
from services.aggregation_service import get_aggregation_service
from services.rekognition_service import get_rekognition_service
from db.supabase_client import get_supabase_client
from models.person import Person
from utils.logger import setup_logger

logger = setup_logger('search_route')

search_bp = Blueprint('search', __name__)

# Create debug directory for step outputs
# DEBUG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'debug_steps')
# os.makedirs(DEBUG_DIR, exist_ok=True)

# def save_step_output(step_number: int, step_name: str, data: any, query: str):
#     """Save step output to a JSON file for debugging and cost savings."""
#     try:
#         # Create safe filename from query
#         safe_query = ''.join(c if c.isalnum() else '_' for c in query)[:50]
#         timestamp = dt.now().strftime('%Y%m%d_%H%M%S')
#         filename = f"step{step_number}_{step_name}_{safe_query}_{timestamp}.json"
#         filepath = os.path.join(DEBUG_DIR, filename)
#         
#         # Convert data to JSON-serializable format
#         if hasattr(data, 'to_dict'):
#             serializable_data = data.to_dict()
#         elif hasattr(data, '__dict__'):
#             serializable_data = data.__dict__
#         else:
#             serializable_data = data
#         
#         with open(filepath, 'w', encoding='utf-8') as f:
#             json.dump({
#                 'step': step_number,
#                 'step_name': step_name,
#                 'query': query,
#                 'timestamp': timestamp,
#                 'data': serializable_data
#             }, f, indent=2, default=str)
#         
#         logger.info(f"💾 Saved step {step_number} output to: {filename}")
#     except Exception as e:
#         logger.warning(f"Failed to save step {step_number} output: {e}")


def normalize_query(query: str) -> str:
    """
    Normalize query for consistent cache lookups
    - Lowercase
    - Strip whitespace
    - Collapse multiple spaces
    - Remove @ prefix if present
    """
    normalized = query.lower().strip()
    normalized = ' '.join(normalized.split())  # Collapse multiple spaces
    if normalized.startswith('@'):
        normalized = normalized[1:]
    return normalized


def validate_social_url(url: str, platform: str) -> bool:
    """
    Validate that a social media URL actually exists (returns 200).
    
    Args:
        url: Social media profile URL to validate
        platform: Platform name (instagram, twitter, linkedin, etc.)
        
    Returns:
        True if URL is accessible (200 status), False otherwise
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=8)
        
        # 200 = OK, 302/301 = Redirect (common for social media)
        if response.status_code in [200, 301, 302]:
            logger.debug(f"✅ Valid {platform} URL: {url}")
            return True
        else:
            logger.debug(f"❌ Invalid {platform} URL (status {response.status_code}): {url}")
            return False
            
    except requests.RequestException as e:
        logger.debug(f"❌ Invalid {platform} URL ({type(e).__name__}): {url}")
        return False
    except Exception as e:
        logger.debug(f"❌ Validation error for {platform} URL: {str(e)}")
        return False


def fetch_google_image_urls(name: str) -> List[Dict]:
    """Fetch up to 5 Google Custom Search image URLs for a name - portrait/face images only."""
    api_key = os.getenv('GOOGLE_API_KEY')
    cx = os.getenv('GOOGLE_CX')

    if not api_key or not cx:
        logger.warning("Google API credentials not set; skipping image fetch")
        return []

    # Use the targeted query (already includes name + occupation + location) with face-focused keywords
    search_query = f"{name} portrait OR profile OR headshot"
    
    params = {
        'q': search_query,
        'cx': cx,
        'key': api_key,
        'searchType': 'image',
        'num': 10,  # Request more to filter down
        'imgType': 'face',  # Google's face detection
        'safe': 'high',
        'imgSize': 'medium',  # Profile pics are usually medium size
        'fileType': 'jpg,png'  # Standard formats
    }

    try:
        response = requests.get('https://www.googleapis.com/customsearch/v1', params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"Google Image Search failed with status {response.status_code}: {response.text}")
            return []

        data = response.json()
        items = data.get('items', []) if isinstance(data, dict) else []

        rekognition = get_rekognition_service()
        photos = []
        for item in items:
            url = item.get('link')
            title = item.get('title', '').lower()
            
            # Skip if title suggests non-person image
            skip_keywords = ['logo', 'icon', 'wallpaper', 'background', 'landscape', 'building', 'product']
            if any(keyword in title for keyword in skip_keywords):
                continue
            
            # Validate image contains a face using AWS Rekognition
            if url and rekognition.validate_image(url):
                photos.append({
                    'url': url,
                    'caption': item.get('title', ''),
                    'likes': None,
                    'source': 'google'
                })
                
            if len(photos) >= 5:  # Only need 5 good ones
                break

        if photos:
            logger.info(f"Fetched and validated {len(photos)} Google portrait images for {name}")

        return photos

    except Exception as e:
        logger.error(f"Error fetching Google images for {name}: {str(e)}")

    return []

@search_bp.route('/search', methods=['POST'])
def search_person():
    """
    Search for information about a person

    Request body:
        {
            "query": "john doe"  # Can be name, email, username, phone, etc.
        }

    Response:
        {
            "personId": "uuid",
            "basic_info": {...},
            "social_profiles": [...],
            "photos": [...],
            "notable_mentions": [...],
            "raw_sources": [...]
        }
    """
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'Query parameter is required'}), 400

        query = data['query'].strip()
        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400

        candidate = data.get('candidate')

        reference_photo_id = data.get('referencePhotoId')
        reference_photo = None
        reference_temp_path = None
        reference_bytes = None
        if reference_photo_id:
            logger.info(f"ReferencePhotoId provided: {reference_photo_id}; downloading from storage")


        # ===== Check for profile existing in cache =====
        normalized_query = normalize_query(query)
        cache_key = normalized_query
        if candidate and candidate.get('id'):
            cache_key = f"{normalized_query}::{candidate.get('id')}"

        supabase_client = get_supabase_client()

        # Check cache first using the specific cache key
        cached_person = supabase_client.get_person_by_query(cache_key)
        if cached_person:
            logger.info(f"Cache hit for '{cache_key}' — returning cached result")
            # Convert cached dict to Person object and return
            person = Person.from_dict(cached_person)
            return jsonify(person.to_response()), 200
        logger.info(f"Cache miss for '{cache_key}' — performing fresh search\n")


        # If we received a referencePhotoId, download the image from Supabase and store locally
        if reference_photo_id:
            try:
                reference_bytes = supabase_client.client.storage.from_('reference-photos').download(reference_photo_id)

                # Persist locally as a temp file for any downstream processing that needs a path
                suffix = os.path.splitext(reference_photo_id)[1] or '.jpg'
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix='ref_download_') as tmp:
                    tmp.write(reference_bytes)
                    reference_temp_path = tmp.name

                # Provide base64 to aggregation for Rekognition verification of photos
                reference_photo = base64.b64encode(reference_bytes).decode('ascii')
                logger.info(f"Downloaded reference image and stored at {reference_temp_path}\n")
            except Exception as e:
                logger.warning(f"Failed to download reference photo '{reference_photo_id}': {e}")
                reference_photo = None


        websearch_service = get_websearch_service()
        apify_service = get_apify_service()
        aggregation_service = get_aggregation_service()


        #  If candidate is provided, use that to guide the search
        if candidate:
            logger.info(f"Deep search requested for candidate: {candidate.get('name')}")
            websearch_result = {
                'source': 'candidate_selection',
                'query': query,
                'content': f"Selected candidate: {candidate.get('name')}. {candidate.get('summary')}",
                'timestamp': None
            }
            
            structured_info = {
                'basic_info': {
                    'name': candidate.get('name'),
                    'occupation': candidate.get('occupation'),
                    'location': candidate.get('location', ''),
                    'education': candidate.get('education') or [],
                    'company': candidate.get('currentCompany', '')
                },
                'social_profiles': [],
                'photos': [{'url': candidate.get('imageUrl'), 'source': 'candidate_selection'}] if candidate.get('imageUrl') else [],
                'notable_mentions': []
            }
            
            logger.info(f"Performing targeted websearch for candidate: {candidate.get('name')} {candidate.get('occupation')} {candidate.get('location', '')}")
            
            websearch_result = websearch_service.search_person(f"{candidate.get('name')} {candidate.get
            ('occupation')} {candidate.get('location', '')}".strip())
            
            new_structured_info = websearch_result.get('structured_data')
            if not new_structured_info or 'error' in websearch_result:
                new_structured_info = websearch_service.extract_structured_info(
                    f"{candidate.get('name')} {candidate.get('occupation')} {candidate.get('location', '')}".strip(),
                    websearch_result.get('content', '')
                )
            
            # Merge candidate info into the new structured info (candidate info takes precedence for name/photo)
            structured_info = new_structured_info
            if candidate.get('name'):
                structured_info.setdefault('basic_info', {})['name'] = candidate.get('name')
            if candidate.get('education'):
                structured_info.setdefault('basic_info', {})['education'] = candidate.get('education')
            if candidate.get('imageUrl'):
                # Prepend candidate photo
                structured_info.setdefault('photos', []).insert(0, {'url': candidate.get('imageUrl'), 'source': 'candidate_selection'})
        
        # else directly search user query 
        else:
            logger.info("Step 1: Performing websearch...")
            websearch_result = websearch_service.search_person(query)
            # save_step_output(1, 'websearch', websearch_result, query)

            logger.info("Step 2: Extracting structured information...")
            structured_info = websearch_result.get('structured_data')
            if not structured_info or 'error' in websearch_result:
                structured_info = websearch_service.extract_structured_info(
                    query,
                    websearch_result.get('content', '')
                )
            # save_step_output(2, 'structured_info', structured_info, query)


        # Step 3: Identify social media handles
        logger.info("Step 3: Identifying social media handles...")
        identifiers = extract_social_identifiers(query, structured_info)
        logger.info(f"Identified social handles: {identifiers}\n")
        # save_step_output(3, 'social_handles', identifiers, query)

        # Fallback: If key social profiles are missing, try to find them via Apify Google Search
        # We check for at least one major platform or if the list is empty
        if not identifiers or (not identifiers.get('instagram') and not identifiers.get('twitter') and not identifiers.get('linkedin')):
            
            logger.info("Key social profiles missing. Attempting fallback search via Apify...\n")
            fallback_links = apify_service.find_social_links(query)
            # save_step_output(3.5, 'fallback_social_links', fallback_links, query)
            
            # Merge fallback links into identifiers for scraping attempts
            if fallback_links:
                logger.info(f"Found social links: {fallback_links}\n")
                identifiers.update(fallback_links)
                
                # Add validated profile URLs to structured_info for final response
                for platform, handle_or_url in fallback_links.items():
                    # Check if already exists to avoid duplicates
                    exists = False
                    for profile in structured_info.get('social_profiles', []):
                        if profile.get('platform') == platform:
                            exists = True
                            break
                    
                    if not exists:
                        # Build proper profile URL
                        if platform == 'instagram':
                            profile_url = f"https://www.instagram.com/{handle_or_url}"
                            username = handle_or_url
                        elif platform == 'twitter':
                            profile_url = f"https://twitter.com/{handle_or_url}"
                            username = handle_or_url
                        elif platform == 'tiktok':
                            profile_url = f"https://www.tiktok.com/@{handle_or_url}"
                            username = handle_or_url
                        elif platform == 'linkedin':
                            profile_url = handle_or_url  # Already full URL
                            username = ''
                        elif platform in ['facebook', 'youtube']:
                            profile_url = handle_or_url  # Already full URL
                            username = ''
                        else:
                            continue
                        
                        # Validate URL before adding
                        if validate_social_url(profile_url, platform):
                            structured_info.setdefault('social_profiles', []).append({
                                'platform': platform,
                                'username': username,
                                'url': profile_url
                            })
                        else:
                            logger.info(f"Skipping invalid {platform} URL: {profile_url}")


        # Step 4: Execute Parallel Tasks (Social Scraping + Answer Generation)
        logger.info("Step 4: Executing parallel tasks (Scraping + Answer Generation)...")
        
        apify_results = []
        generated_answer = None
        related_questions = []
        pdl_data = None
        answer_generated_at = None

        from concurrent.futures import ThreadPoolExecutor
        from services.answer_service import get_answer_service
        from datetime import datetime

        answer_service = get_answer_service()

        def run_scraping():
            results = []
            if identifiers:
                results.extend(apify_service.scrape_all_parallel(query, identifiers))
            
            # OSINT Scraping
            # We try to determine location and age from candidate or structured_info
            search_location = ""
            
            if candidate and candidate.get('location'):
                search_location = candidate.get('location')
            elif structured_info and structured_info.get('basic_info', {}).get('location'):
                search_location = structured_info.get('basic_info', {}).get('location')
            
            # If we selected a candidate, use that name. Otherwise use query.
            search_name = candidate.get('name') if candidate else query
            
            # Run OSINT in parallel within this thread or let scrape_osint handle it
            # scrape_osint returns a list of result dicts
            osint_results = apify_service.scrape_osint(search_name, search_location)
            if osint_results:
                results.extend(osint_results)
                
            return results

        def run_answer_generation():
            # Use structured_info as the base for the answer
            # We construct a temporary "person_data" dict for the answer service
            temp_person_data = {
                'query': query,
                'basic_info': structured_info.get('basic_info', {}),
                'social_profiles': structured_info.get('social_profiles', []),
                'notable_mentions': structured_info.get('notable_mentions', []),
                'candidate_description': candidate.get('description') if candidate else None
            }
            try:
                # Use low verbosity to prevent timeouts
                ans = answer_service.generate_answer(temp_person_data)
                qs = answer_service.generate_related_questions(query, temp_person_data)
                return ans, qs
            except Exception as e:
                logger.error(f"Error generating answer in background: {e}")
                return None, []

        def run_pdl_enrichment():
            pdl_params = {}
            # 1. Use PDL ID if available from candidate (best match)
            if candidate and candidate.get('pdl_id'):
                pdl_params['pdl_id'] = candidate.get('pdl_id')
            
            # 2. Use LinkedIn if available
            elif identifiers.get('linkedin'):
                 pdl_params['profile'] = identifiers['linkedin']
                 
            # 3. Use Name + Location if available (and name is not just a username)
            elif candidate and candidate.get('name') and not candidate.get('name').startswith('@'):
                 # Simple name enrichment is risky without location/company, but we can try
                 # if we have location in basic info (which we might typically lack at this stage unless from input)
                 # Let's rely on explicit IDs or URLs for now to be safe and cost-effective.
                 pass
                 
            if pdl_params:
                 try:
                     from services.pdl_service import get_pdl_service
                     pdl_service = get_pdl_service()
                     return pdl_service.enrich_person(pdl_params)
                 except Exception as e:
                     logger.error(f"Error running PDL enrichment: {e}")
                     return None
            return None

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_scraping = executor.submit(run_scraping)
            future_answer = executor.submit(run_answer_generation)
            # future_pdl = executor.submit(run_pdl_enrichment)

            # Wait for all to complete
            apify_results = future_scraping.result()
            generated_answer, related_questions = future_answer.result()
            # pdl_data = future_pdl.result()
            
            if generated_answer:
                answer_generated_at = datetime.utcnow()

            logger.info("Parallel tasks completed.\n")
            
            # Save step 4 outputs
            # save_step_output(4, 'apify_results', apify_results, query)
            # save_step_output(4, 'answer_generation', {
            #     'answer': generated_answer,
            #     'related_questions': related_questions,
            #     'answer_generated_at': answer_generated_at.isoformat() if answer_generated_at else None
            # }, query)
            # save_step_output(4, 'pdl_data', pdl_data, query)


        # Step 5: Aggregate all data
        logger.info("Step 5: Aggregating data from all sources...")
        aggregated_data = aggregation_service.aggregate_person_data(
            query,
            websearch_result,
            apify_results,
            structured_info,
            # pdl_data,
            reference_photo=reference_photo  # Pass reference photo for Phase 2 verification
        )
        # save_step_output(5, 'aggregated_data', aggregated_data, query)

        # Step 5.5: Google image fallback (triggers when no photos or all proxying failed)
        existing_photos = aggregated_data.get("photos", [])
        if existing_photos:
            logger.info(f"Found {len(existing_photos)} photos from direct sources; skipping Google fallback.\n")
        else:
            logger.info("No photos from direct sources; fetching from Google Images...")
            basic_info = aggregated_data.get('basic_info', {})
            name = basic_info.get('name', query)
            occupation = basic_info.get('occupation', '')
            location = basic_info.get('location', '')
            
            targeted_query = f"{name} {occupation} {location}".strip()
            if not targeted_query:
                targeted_query = query
                
            google_photos = fetch_google_image_urls(targeted_query)
            if google_photos:
                logger.info(f"Google Images provided {len(google_photos)} photos\n")
                aggregated_data["photos"] = google_photos
            else:
                logger.warning("Google Images fallback also returned no photos\n")
                aggregated_data["photos"] = []
            # save_step_output(5.5, 'google_fallback', google_photos if google_photos else [], query)

        # Step 6: Create Person object
        logger.info("Step 6: Creating Person object...\n")
        person = Person(
            query=cache_key,
            basic_info=aggregated_data.get('basic_info'),
            social_profiles=aggregated_data.get('social_profiles'),
            photos=aggregated_data.get('photos'),
            notable_mentions=aggregated_data.get('notable_mentions'),
            raw_sources=aggregated_data.get('raw_sources'),
            answer=generated_answer,
            related_questions=related_questions,
            answer_generated_at=answer_generated_at
        )
        # save_step_output(6, 'person_object', person.to_dict(), query)

        # Step 7: Store in Supabase
        logger.info("Step 7: Storing results in database...\n")
        stored_person = supabase_client.create_person(person.to_dict())

        if not stored_person:
            logger.error("Failed to store person in database\n")
            return jsonify({'error': 'Failed to store results'}), 500

        # Update person with ID from database
        person.id = stored_person['id']
        # save_step_output(7, 'database_stored', stored_person, query)

        logger.info(f"Search completed successfully for query: {query}")

        response_json = jsonify(person.to_response())
        if reference_temp_path and os.path.exists(reference_temp_path):
            try:
                os.remove(reference_temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp reference file: {reference_temp_path} ({e})")
        return response_json, 200

    except Exception as e:
        logger.error(f"Error in search endpoint: {str(e)}", exc_info=True)
        if 'reference_temp_path' in locals() and reference_temp_path and os.path.exists(reference_temp_path):
            try:
                os.remove(reference_temp_path)
            except Exception:
                pass
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


@search_bp.route('/report', methods=['POST'])
def report_person():
    """
    Report a person profile
    
    Request body:
        { "personId": "uuid" }
    """
    try:
        data = request.get_json()
        if not data or 'personId' not in data:
            return jsonify({'error': 'personId is required'}), 400
            
        person_id = data['personId']
        supabase_client = get_supabase_client()
        
        success = supabase_client.increment_report_count(person_id)
        
        if success:
            return jsonify({'message': 'Report submitted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to submit report'}), 500
            
    except Exception as e:
        logger.error(f"Error in report endpoint: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def extract_social_identifiers(query: str, structured_info: Dict) -> Dict[str, str]:
    """
    Extract social media identifiers from query and structured info

    Args:
        query: The original search query
        structured_info: Structured information extracted from websearch

    Returns:
        Dictionary mapping platforms to usernames/URLs
    """
    identifiers = {}

    # Check if query looks like a social media handle
    if query.startswith('@'):
        username = query[1:]
        identifiers['instagram'] = username
        identifiers['twitter'] = username

    # Extract from social_profiles in structured_info
    social_profiles = structured_info.get('social_profiles', [])

    for profile in social_profiles:
        platform = profile.get('platform', '').lower()
        url = profile.get('url', '')
        username = profile.get('username', '')

        if platform == 'instagram' and username:
            identifiers['instagram'] = username
        elif platform == 'twitter' and username:
            identifiers['twitter'] = username
        elif platform == 'linkedin' and url:
            identifiers['linkedin'] = url

    return identifiers
