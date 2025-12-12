from flask import Blueprint, request, jsonify
import os
import tempfile
import uuid
from typing import List, Dict
from datetime import datetime

from services.websearch_service import get_websearch_service
from services.serpapi_service import get_serpapi_service
from services.rekognition_service import get_rekognition_service
from db.supabase_client import get_supabase_client
from utils.logger import setup_logger

logger = setup_logger('candidates_route')

candidates_bp = Blueprint('candidates', __name__)


def _ensure_ids(candidates: List[Dict]) -> List[Dict]:
    """Attach stable ids to candidates."""
    for idx, cand in enumerate(candidates):
        cand['id'] = str(cand.get('id') or cand.get('name') or f"candidate-{idx}")
    return candidates


def _rank_by_score(candidates: List[Dict]) -> List[Dict]:
    """Sort by similarityScore desc and assign rank."""
    scored = sorted(candidates, key=lambda c: float(c.get('similarityScore') or 0), reverse=True)
    for i, cand in enumerate(scored, start=1):
        cand['rank'] = i
    return scored

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


@candidates_bp.route('/candidates/ranked', methods=['POST'])
def get_candidates_ranked():
    """New endpoint: same pipeline as /candidates, plus optional Rekognition rerank."""
    temp_path = None
    reference_bytes = None

    try:
        # Read query and refinements from query params or form-data
        base_query = (request.args.get('query') or request.form.get('query') or '').strip()
        if not base_query:
            return jsonify({'error': 'query is required'}), 400

        def _param(key: str) -> str:
            return (request.args.get(key) or request.form.get(key) or '').strip()

        age = _param('age')
        location = _param('location')
        school = _param('school')
        company = _param('company')
        social = _param('social')

        query_parts = [base_query]
        if age: query_parts.append(f"age {age}")
        if location: query_parts.append(location)
        if school: query_parts.append(school)
        if company: query_parts.append(company)
        if social: query_parts.append(social)
        refined_query = " ".join(query_parts)

        # Optional file upload for reference image
        reference_file = request.files.get('file')
        if reference_file and reference_file.filename:
            logger.info(f"Reference file uploaded: {reference_file.filename}\n")
            try:
                suffix = os.path.splitext(reference_file.filename)[1] or '.jpg'
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix='ref_photo_') as tmp:
                    reference_file.save(tmp.name)
                    temp_path = tmp.name
                with open(temp_path, 'rb') as fh:
                    reference_bytes = fh.read()
            except Exception as e:
                logger.warning(f"Failed to read uploaded reference file: {e}\n")
                reference_bytes = None
        else:
            logger.info("No reference file uploaded in request\n")

        candidates = []

        # Try PDL first (same as existing route)
        try:
            from services.pdl_service import get_pdl_service
            pdl_service = get_pdl_service()
            candidates = pdl_service.search_person(
                name=base_query,
                age=age,
                location=location,
                school=school,
                company=company,
                social=social
            ) or []
        except Exception as e:
            logger.warning(f"PDL search failed in ranked flow: {e}\n")
            candidates = []

        # If PDL returned nothing, fall back to SerpAPI
        if not candidates:
            logger.info("PDL returned no candidates, falling back to SerpAPI\n")
            serpapi_service = get_serpapi_service()
            candidates = serpapi_service.fetch_candidates(refined_query) or []
            logger.info(f"SerpAPI returned {len(candidates)} candidates\n")
        else:
            logger.info(f"PDL returned {len(candidates)} candidates\n")

        # Hydrate images for all candidates (PDL or SerpAPI)
        # Top 5 only to save time/quota
        if candidates:
            from concurrent.futures import ThreadPoolExecutor
            serpapi_service = get_serpapi_service()

            def fetch_image(candidate):
                try:
                    query_bits = [candidate.get('name', '')]
                    desc = candidate.get('description', '')
                    if ' at ' in desc:
                        company_part = desc.split(' at ')[1].split(' • ')[0]
                        query_bits.append(company_part)
                    image_url = serpapi_service.fetch_image_url(" ".join(query_bits))
                    if image_url:
                        candidate['imageUrl'] = image_url
                        logger.info(f"Fetched image for '{candidate.get('name')}': {image_url}")
                    else:
                        logger.info(f"No image found for '{candidate.get('name')}'")
                except Exception as e:
                    logger.warning(f"Image fetch failed for {candidate.get('name')}: {e}")
                return candidate

            top = candidates[:5]
            rest = candidates[5:]
            with ThreadPoolExecutor(max_workers=5) as executor:
                top = [f.result() for f in [executor.submit(fetch_image, c) for c in top]]
            candidates = top + rest
            logger.info(f"Image hydration complete. Top {len(top)} processed.\n")

        if not candidates:
            return jsonify({'query': base_query, 'candidates': []}), 200

        _ensure_ids(candidates)

        # Dedup for non-PDL, same as original route
        is_pdl = 'pdl_id' in candidates[0]
        if not is_pdl:
            logger.info(f"Running LLM deduplication for {len(candidates)} non-PDL candidates")
            try:
                websearch_service = get_websearch_service()
                candidates = websearch_service.deduplicate_candidates(candidates)
                logger.info(f"After deduplication: {len(candidates)} candidates remain")
            except Exception as e:
                logger.warning(f"Dedup failed in ranked flow: {e}")
        else:
            logger.info("Skipping LLM deduplication for PDL candidates")

        # Store reference photo in Supabase bucket if provided
        reference_photo_id = None
        if reference_bytes:
            try:
                supabase = get_supabase_client()
                photo_id = f"{datetime.utcnow().isoformat()}_{uuid.uuid4()}.jpg"
                supabase.client.storage.from_('reference-photos').upload(
                    path=photo_id,
                    file=reference_bytes,
                    file_options={"content-type": "image/jpeg"}
                )
                reference_photo_id = photo_id
                logger.info(f"Stored reference photo in bucket: {reference_photo_id}")
            except Exception as e:
                logger.warning(f"Failed to store reference photo: {e}")

        # If no reference file, just rank by current order with zero scores
        if not reference_bytes:
            logger.info("No reference image provided; returning candidates with similarityScore=0")
            for idx, c in enumerate(candidates, start=1):
                c['similarityScore'] = 0.0
                c['rank'] = idx
            return jsonify({'query': base_query, 'candidates': candidates, 'referencePhotoId': reference_photo_id}), 200

        logger.info(f"Starting Rekognition face comparison for {len(candidates)} candidates")
        rekognition = get_rekognition_service()

        for cand in candidates:
            similarity = 0.0
            image_url = cand.get('imageUrl')
            if image_url:
                logger.info(f"Comparing reference with candidate '{cand.get('name')}' image: {image_url}")
                try:
                    similarity = rekognition.compare_faces_bytes(reference_bytes, image_url) or 0.0
                    logger.info(f"  -> Similarity: {similarity}")
                except Exception as e:
                    logger.warning(f"Rekognition compare failed for candidate {cand.get('id')}: {e}")
            else:
                logger.info(f"Candidate '{cand.get('name')}' has no imageUrl; skipping comparison")
            cand['similarityScore'] = round(similarity, 2)

        candidates = _rank_by_score(candidates)
        logger.info(f"Ranking complete. Top candidate: {candidates[0].get('name')} with score {candidates[0].get('similarityScore')}")
        return jsonify({'query': base_query, 'candidates': candidates, 'referencePhotoId': reference_photo_id}), 200

    except Exception as e:
        logger.error(f"Error in /candidates/ranked: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                logger.warning(f"Failed to remove temp reference file: {temp_path}")
