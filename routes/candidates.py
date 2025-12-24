from flask import Blueprint, request, jsonify
import os
import tempfile
import uuid
from typing import List, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from services.websearch_service import get_websearch_service
from services.serpapi_service import get_serpapi_service
from services.rekognition_service import get_rekognition_service
from db.supabase_client import get_supabase_client
from utils.logger import setup_logger
from utils.image_utils import validate_image_url

logger = setup_logger('candidates_route')

candidates_bp = Blueprint('candidates', __name__)


def _rank_by_score(candidates: List[Dict]) -> List[Dict]:
    """Sort by similarityScore desc and assign rank."""
    scored = sorted(candidates, key=lambda c: float(c.get('similarityScore') or 0), reverse=True)
    for i, cand in enumerate(scored, start=1):
        cand['rank'] = i
    return scored


def fetch_multiple_images_with_dedup(candidates, serpapi_service, rekognition_service):
    """
    Fetch multiple images per candidate and assign unique faces using face recognition
    """
    logger.info(f"Fetching multiple images for {len(candidates)} candidates with face-based deduplication\n")
    
    # Track face embeddings we've already assigned
    assigned_embeddings = []
    
    for candidate in candidates:
        name = candidate.get('name', '')
        candidate['imageUrl'] = None  # Reset
        
        # Fetch top 5 image results for this candidate (simple name query)
        logger.info(f"Fetching images for: {name}")
        image_urls = serpapi_service.fetch_multiple_images(name, count=5)
        
        if not image_urls:
            continue
        
        # Try each image until we find a unique face
        for img_url in image_urls:
            try:
                # Get face embedding from this image
                embedding = rekognition_service.get_face_embedding(img_url)
                
                if not embedding:
                    continue
                
                # Check if this face is similar to any we've already assigned
                is_duplicate = False
                for assigned_emb in assigned_embeddings:
                    if rekognition_service.are_faces_similar(embedding, assigned_emb):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    # This is a unique face!
                    candidate['imageUrl'] = img_url
                    assigned_embeddings.append(embedding)
                    logger.info(f"  ✅ Assigned unique image to '{name}'\n")
                    break
                    
            except Exception as e:
                continue
        
        if not candidate.get('imageUrl'):
            logger.info(f"❌ Could not find unique face for '{name}'\n")
    
    with_images = sum(1 for c in candidates if c.get('imageUrl'))
    logger.info(f"Face-based deduplication complete: {with_images}/{len(candidates)} candidates have unique images\n")
    
    return candidates


@candidates_bp.route('/candidates/ranked', methods=['POST'])
def get_candidates_ranked():
    temp_path = None
    reference_bytes = None

    try:
        base_query = (request.args.get('query') or request.form.get('query') or '').strip()
        if not base_query:
            return jsonify({'error': 'query is required', 'message': 'Missing query parameter'}), 400

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

        logger.info(f"Refined query: {refined_query}\n")

        # Optional file upload for reference image
        reference_photo_id = None
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
                
                # Store reference photo in Supabase bucket
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
            except Exception as e:
                logger.warning(f"Failed to read uploaded reference file: {e}\n")
                reference_bytes = None
        else:
            logger.info("No reference file uploaded in request\n")


        candidates = []

        websearch_service = get_websearch_service()
        candidates = websearch_service.fetch_candidates_from_web(refined_query, max_candidates=6) or []
        logger.info(f"Claude web search returned {len(candidates)} candidates\n")

        if not candidates:
            return jsonify({'query': refined_query, 'candidates': [], 'message': 'No candidates found from Claude web search'}), 200


        # Fetch multiple images with face-based deduplication
        serpapi_service = get_serpapi_service()
        rekognition_service = get_rekognition_service()
        candidates = fetch_multiple_images_with_dedup(candidates, serpapi_service, rekognition_service)

        # Deduplicate by image URL - keep first occurrence of each unique image
        unique_candidates = []
        seen_images = set()
        for cand in candidates:
            img_url = cand.get('imageUrl')
            
            # Keep candidates without images
            if not img_url:
                unique_candidates.append(cand)
                continue
            
            # Skip if we've seen this image before
            if img_url in seen_images:
                logger.info(f"Skipping duplicate image for '{cand.get('name')}': {img_url}")
                continue
            
            # New unique image - keep it
            unique_candidates.append(cand)
            seen_images.add(img_url)

        candidates = unique_candidates
        logger.info(f"After image deduplication: {len(candidates)} unique candidates remain\n")

        # Attach stable ids to candidates
        for idx, cand in enumerate(candidates):
            cand['id'] = str(cand.get('id') or cand.get('name') or f"candidate-{idx}")

        # # Run LLM deduplication for SerpAPI candidates
        # logger.info(f"Running LLM deduplication for {len(candidates)} candidates")
        # try:
        #     websearch_service = get_websearch_service()
        #     candidates = websearch_service.deduplicate_candidates(candidates)
        #     logger.info(f"After deduplication: {len(candidates)} candidates remain\n")
        # except Exception as e:
        #     logger.warning(f"Dedup failed: {e}")

        # Validate candidate images and filter out non-face images
        logger.info(f"Validating candidate images for {len(candidates)} candidates")
        rekognition = get_rekognition_service()
        
        final_candidates = []
        for cand in candidates:
            image_url = cand.get('imageUrl')
            
            # No image URL: keep candidate (will have similarityScore=0) 
            if not image_url:
                logger.info(f"Candidate '{cand.get('name')}' has no imageUrl; keeping in results")
                cand['hasFaceImage'] = False
                final_candidates.append(cand)
                continue
            
            # Has image URL: validate it contains a face
            if rekognition.validate_image(image_url):
                logger.info(f"✅ '{cand.get('name')}' has valid face image")
                cand['hasFaceImage'] = True
                final_candidates.append(cand)
            else:
                # Image exists but no face (landscape/logo/etc) - DISCARD
                logger.info(f"❌ Discarding '{cand.get('name')}' - image has no face: {image_url}")
        
        candidates = final_candidates
        face_count = sum(1 for c in candidates if c.get('hasFaceImage', False))
        no_image_count = sum(1 for c in candidates if not c.get('imageUrl'))
        logger.info(f"After validation: {len(candidates)} candidates remain ({face_count} with face images, {no_image_count} without images)\n")
        
        if not candidates:
            logger.info("No candidates remaining after validation")
            return jsonify({'query': refined_query, 'candidates': [], 'referencePhotoId': reference_photo_id, 'message': 'No valid candidates found'}), 200
        
        # If no reference file, return all candidates with zero scores
        if not reference_bytes:
            logger.info("No reference image provided; returning all candidates with similarityScore=0")
            for idx, c in enumerate(candidates, start=1):
                c['similarityScore'] = 0.0
                c['rank'] = idx
            return jsonify({'query': refined_query, 'candidates': candidates, 'referencePhotoId': reference_photo_id, 'message': 'No reference image provided; returning all candidates with similarityScore=0'}), 200

        # Compare reference photo with candidates that have face images
        logger.info(f"Starting face comparison for {face_count} candidates with valid face images")

        for cand in candidates:
            similarity = 0.0
            
            # Only compare candidates with valid face images
            if cand.get('hasFaceImage', False):
                image_url = cand.get('imageUrl')
                logger.info(f"Comparing '{cand.get('name')}': {image_url}")
                try:
                    similarity = rekognition.compare_faces_bytes(reference_bytes, image_url, 70.0) or 0.0
                    logger.info(f"  -> Similarity: {similarity}%")
                except Exception as e:
                    logger.warning(f"Comparison failed for '{cand.get('name')}': {e}")
            
            cand['similarityScore'] = round(similarity, 2)

        # Sort by similarity score (candidates without images will be at bottom with score=0)
        candidates = _rank_by_score(candidates)
        logger.info(f"Ranking complete. Top candidate: '{candidates[0].get('name')}' with score {candidates[0].get('similarityScore')}%")
        return jsonify({'query': refined_query, 'candidates': candidates, 'referencePhotoId': reference_photo_id, 'message': 'Face comparison completed'}), 200

    except Exception as e:
        logger.error(f"Error in /candidates/ranked: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                logger.warning(f"Failed to remove temp reference file: {temp_path}")
