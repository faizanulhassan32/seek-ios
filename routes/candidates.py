from flask import Blueprint, request, jsonify
from services.websearch_service import get_websearch_service
from services.serpapi_service import get_serpapi_service
from utils.logger import setup_logger

logger = setup_logger('candidates_route')

candidates_bp = Blueprint('candidates', __name__)

@candidates_bp.route('/candidates', methods=['POST'])
def get_candidates():
    """
    Find potential person candidates
    
    Request body:
        { "query": "name" }
        
    Response:
        {
            "candidates": [
                {
                    "id": "id",
                    "name": "Name",
                    "description": "Short summary",
                    "imageUrl": "url"
                }
            ]
        }
    """
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'Query parameter is required'}), 400
            
        base_query = data['query'].strip()
        if not base_query:
            return jsonify({'error': 'Query cannot be empty'}), 400
            
        # Extract advanced search fields
        # Extract advanced search fields
        # Handle None values safely (in case frontend sends null)
        age = str(data.get('age') or '').strip()
        location = str(data.get('location') or '').strip()
        school = str(data.get('school') or '').strip()
        company = str(data.get('company') or '').strip()
        social = str(data.get('social') or '').strip()
        
        # Construct refined query
        query_parts = [base_query]
        if age: query_parts.append(f"age {age}")
        if location: query_parts.append(location)
        if school: query_parts.append(school)
        if company: query_parts.append(company)
        if social: query_parts.append(social)
        
        refined_query = " ".join(query_parts)
        
        logger.info(f"Received candidate search request. Base: {base_query}, Refined: {refined_query}")
        
        # 1. Try PDL Search first
        from services.pdl_service import get_pdl_service
        pdl_service = get_pdl_service()
        
        # Only use PDL if we have at least one advanced param OR if specifically desired
        # For now, always try PDL if key is present
        candidates = pdl_service.search_person(
            name=base_query,
            age=age,
            location=location,

            school=school,
            company=company,
            social=social
        )
        
        if candidates:
            logger.info(f"Found {len(candidates)} candidates via PDL Search")
            
            # Hydrate with images from Google Images (SerpApi) in parallel
            # We only do this for the top 5 to save time/quota
            from concurrent.futures import ThreadPoolExecutor
            serpapi_service = get_serpapi_service()
            
            def fetch_image(candidate):
                try:
                    # Construct query: Name + Title + Company
                    # e.g. "John Doe Software Engineer Google"
                    query_parts = [candidate['name']]
                    
                    # Parse description to get title/company if possible, or just use what we have
                    # PDL candidates have 'description' field formatted as "Title at Company • Location"
                    # But we also have raw data if we wanted, but let's use the description or name
                    # Actually, let's just use Name + "linkedin" or Name + Company if available in description
                    
                    # Simple heuristic: Name + "profile picture" or just Name
                    # Better: Name + Company if in description
                    desc = candidate.get('description', '')
                    if ' at ' in desc:
                        company_part = desc.split(' at ')[1].split(' • ')[0]
                        query_parts.append(company_part)
                    
                    query = " ".join(query_parts)
                    image_url = serpapi_service.fetch_image_url(query)
                    if image_url:
                        candidate['imageUrl'] = image_url
                except:
                    pass
                return candidate

            with ThreadPoolExecutor(max_workers=5) as executor:
                # Process top 5 candidates
                top_candidates = candidates[:5]
                remaining_candidates = candidates[5:]
                
                futures = [executor.submit(fetch_image, c) for c in top_candidates]
                hydrated_top = [f.result() for f in futures]
                
                candidates = hydrated_top + remaining_candidates
        else:
            logger.info("PDL Search returned no candidates, falling back to SerpApi")
            
            # 2. Fallback to SerpApi
            serpapi_service = get_serpapi_service()
            candidates = serpapi_service.fetch_candidates(refined_query)
        
        if candidates:
            logger.info(f"Found {len(candidates)} candidates (Source: {'PDL' if 'pdl_id' in candidates[0] else 'SerpApi'})")
            
            # Deduplicate using LLM only if NOT from PDL
            # PDL data is structured enough; LLM deduplication is slow and redundant
            is_pdl = 'pdl_id' in candidates[0]
            if not is_pdl:
                logger.info("Running LLM deduplication for non-PDL candidates")
                websearch_service = get_websearch_service()
                candidates = websearch_service.deduplicate_candidates(candidates)
            else:
                logger.info("Skipping LLM deduplication for PDL candidates")
            
            return jsonify({'candidates': candidates}), 200
            
        # 2. Fallback to WebSearchService (AI)
        logger.info("SerpApi returned no candidates, falling back to AI search")
        websearch_service = get_websearch_service()
        websearch_service = get_websearch_service()
        candidates = websearch_service.find_candidates(base_query)
        
        return jsonify({'candidates': candidates}), 200
        
    except Exception as e:
        logger.error(f"Error in candidates endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
