from flask import Blueprint, request, jsonify
from typing import Dict, List, Optional
import os
import requests
import base64
import tempfile
from services.websearch_service import get_websearch_service
from services.apify_service import get_apify_service
from services.aggregation_service import get_aggregation_service
from db.supabase_client import get_supabase_client
from models.person import Person
from utils.logger import setup_logger

logger = setup_logger('search_route')

search_bp = Blueprint('search', __name__)


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


def validate_image_url(url: str) -> bool:
    """
    Validate that an image URL returns a valid image.

    Args:
        url: Image URL to validate

    Returns:
        True if URL returns 200 status with image/* content-type, False otherwise
    """
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


def fetch_google_image_urls(name: str) -> List[Dict]:
    """Fetch up to 5 Google Custom Search image URLs for a name."""
    api_key = os.getenv('GOOGLE_API_KEY')
    cx = os.getenv('GOOGLE_CX')

    if not api_key or not cx:
        logger.warning("Google API credentials not set; skipping image fetch")
        return []

    params = {
        'q': name,
        'cx': cx,
        'key': api_key,
        'searchType': 'image',
        'num': 5,
        'imgType': 'face',
        'safe': 'high'
    }

    try:
        response = requests.get('https://www.googleapis.com/customsearch/v1', params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"Google Image Search failed with status {response.status_code}: {response.text}")
            return []

        data = response.json()
        items = data.get('items', []) if isinstance(data, dict) else []

        photos = []
        for item in items[:5]:
            url = item.get('link')
            if url and validate_image_url(url):
                photos.append({
                    'url': url,
                    'caption': item.get('title', ''),
                    'likes': None,
                    'source': 'google'
                })

        if photos:
            logger.info(f"Fetched and validated {len(photos)} Google images for {name}")

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
        # Validate request
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'Query parameter is required'}), 400

        query = data['query'].strip()
        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400

        # Optional reference photo for Phase 2 face verification via Supabase ID
        reference_photo_id = data.get('referencePhotoId')
        reference_photo = None  # base64 populated only after download
        reference_temp_path = None
        reference_bytes = None
        if reference_photo_id:
            logger.info(f"ReferencePhotoId provided: {reference_photo_id}; downloading from storage")

        # Normalize query for cache lookup
        normalized_query = normalize_query(query)
        
        # Check if we have a selected candidate to skip initial search
        candidate = data.get('candidate')
        
        # Construct cache key
        # If candidate is selected, append candidate ID to query to differentiate 
        # between different people with the same name (e.g. "John Smith" vs "John Smith")
        cache_key = normalized_query
        if candidate and candidate.get('id'):
            cache_key = f"{normalized_query}::{candidate.get('id')}"

        # Initialize Supabase client
        supabase_client = get_supabase_client()

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

        # Check cache first using the specific cache key
        # If a reference photo ID is provided, bypass cache to ensure verification is applied
        cached_person = None
        if not reference_photo_id:
            cached_person = supabase_client.get_person_by_query(cache_key)
        if cached_person:
            logger.info(f"Cache hit for '{cache_key}' — returning cached result")
            # Convert cached dict to Person object and return
            person = Person.from_dict(cached_person)
            return jsonify(person.to_response()), 200

        logger.info(f"Cache miss for '{cache_key}' — performing fresh search\n")
        # Initialize services for fresh search
        websearch_service = get_websearch_service()
        apify_service = get_apify_service()
        aggregation_service = get_aggregation_service()


        if candidate:
            logger.info(f"Deep search requested for candidate: {candidate.get('name')}")
            # Use candidate info as the base for structured data
            websearch_result = {
                'source': 'candidate_selection',
                'query': query,
                'content': f"Selected candidate: {candidate.get('name')}. {candidate.get('summary')}",
                'timestamp': None
            }
            
            # Construct structured info from candidate data
            structured_info = {
                'basic_info': {
                    'name': candidate.get('name'),
                    'occupation': candidate.get('summary'), # Use summary as occupation/desc
                    'location': '', # We might not have this yet
                    'education': [],
                    'company': ''
                },
                'social_profiles': [], # Will be filled by extraction or scraping
                'photos': [{'url': candidate.get('imageUrl'), 'source': 'candidate_selection'}] if candidate.get('imageUrl') else [],
                'notable_mentions': []
            }
            
            # We still might want to do a targeted web search to fill in gaps if needed,
            # but for now let's assume we proceed to extraction/scraping.
            # Actually, to get social profiles, we probably DO need a targeted web search 
            # if the candidate object doesn't have them.
            # Let's do a targeted search for the specific candidate name to get social profiles.
            logger.info(f"Performing targeted websearch for candidate: {candidate.get('name')}")
            websearch_result = websearch_service.search_person(candidate.get('name'))
            
            # Extract structured info from this new search
            new_structured_info = websearch_result.get('structured_data')
            if not new_structured_info or 'error' in websearch_result:
                new_structured_info = websearch_service.extract_structured_info(
                    candidate.get('name'),
                    websearch_result.get('content', '')
                )
            
            # Merge candidate info into the new structured info (candidate info takes precedence for name/photo)
            structured_info = new_structured_info
            if candidate.get('name'):
                structured_info.setdefault('basic_info', {})['name'] = candidate.get('name')
            if candidate.get('imageUrl'):
                # Prepend candidate photo
                structured_info.setdefault('photos', []).insert(0, {'url': candidate.get('imageUrl'), 'source': 'candidate_selection'})

        else:
            # Step 1: Perform websearch (Legacy flow or direct search)
            logger.info("Step 1: Performing websearch...")
            websearch_result = websearch_service.search_person(query)

            # Step 2: Extract structured information from websearch
            logger.info("Step 2: Extracting structured information...")
            structured_info = websearch_result.get('structured_data')
            if not structured_info or 'error' in websearch_result:
                structured_info = websearch_service.extract_structured_info(
                    query,
                    websearch_result.get('content', '')
                )

        # Step 3: Identify social media handles
        logger.info("Step 3: Identifying social media handles...")
        identifiers = extract_social_identifiers(query, structured_info)
        logger.info(f"Identified social handles: {identifiers}\n")

        # Fallback: If key social profiles are missing, try to find them via Apify Google Search
        # We check for at least one major platform or if the list is empty
        if not identifiers or (not identifiers.get('instagram') and not identifiers.get('twitter') and not identifiers.get('linkedin')):
            
            logger.info("Key social profiles missing. Attempting fallback search via Apify...\n")
            fallback_links = apify_service.find_social_links(query)
            
            # Merge fallback links into identifiers
            if fallback_links:
                logger.info(f"Merging fallback links: {fallback_links}\n")
                identifiers.update(fallback_links)
                
                # Also update structured_info so it's reflected in the final response
                for platform, handle_or_url in fallback_links.items():
                    # Check if already exists to avoid duplicates
                    exists = False
                    for profile in structured_info.get('social_profiles', []):
                        if profile.get('platform') == platform:
                            exists = True
                            break
                    
                    if not exists:
                        structured_info.setdefault('social_profiles', []).append({
                            'platform': platform,
                            'username': handle_or_url if platform in ['instagram', 'twitter', 'tiktok'] else '',
                            'url': handle_or_url if 'http' in handle_or_url else f"https://{platform}.com/{handle_or_url}"
                        })

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
            future_pdl = executor.submit(run_pdl_enrichment)

            # Wait for all to complete
            apify_results = future_scraping.result()
            generated_answer, related_questions = future_answer.result()
            pdl_data = future_pdl.result()
            
            if generated_answer:
                answer_generated_at = datetime.utcnow()

            logger.info("Parallel tasks completed.\n")


        # Step 5: Aggregate all data
        logger.info("Step 5: Aggregating data from all sources...")
        aggregated_data = aggregation_service.aggregate_person_data(
            query,
            websearch_result,
            apify_results,
            structured_info,
            pdl_data,
            reference_photo=reference_photo  # Pass reference photo for Phase 2 verification
        )

        # Step 5.5: Google image fallback (triggers when no photos or all proxying failed)
        existing_photos = aggregated_data.get("photos", [])
        if existing_photos:
            logger.info(f"Found {len(existing_photos)} photos from direct sources; skipping Google fallback.\n")
        else:
            logger.info("No photos from direct sources; fetching from Google Images...")
            google_photos = fetch_google_image_urls(query)
            if google_photos:
                logger.info(f"Google Images provided {len(google_photos)} photos\n")
                aggregated_data["photos"] = google_photos
            else:
                logger.warning("Google Images fallback also returned no photos\n")
                aggregated_data["photos"] = []

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

        # Step 7: Store in Supabase
        logger.info("Step 7: Storing results in database...\n")
        stored_person = supabase_client.create_person(person.to_dict())

        if not stored_person:
            logger.error("Failed to store person in database\n")
            return jsonify({'error': 'Failed to store results'}), 500

        # Update person with ID from database
        person.id = stored_person['id']

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
