# Phase 2 – Deep Search & Photo Verification

**Status**: ✅ Implemented  
**Builds on**: Phase 1 (Candidate Finding & Reranking)

---

## Overview

Phase 2 extends the `/search` endpoint with **optional photo verification**. After a user selects a candidate from Phase 1 results, the system performs a deep search and verifies all scraped photos against the reference image using AWS Rekognition.

**Workflow**:
1. User selects a candidate from Phase 1 (e.g., Candidate #1 with 95% match)
2. Client sends the candidate info + same reference photo to `/search`
3. Backend scrapes social media & OSINT sources
4. **[NEW in Phase 2]** Rekognition verifies each scraped photo (only keep 90%+ matches)
5. Returns filtered results with high-confidence photos only

---

## Endpoint

### POST `/search`

**Request** (with Phase 2 reference photo):
```json
{
  "query": "Elon musk",
  "candidate": {
    "id": "Elon Musk",
    "name": "Elon Musk",
    "summary": "Businessman and entrepreneur",
    "imageUrl": "https://..."
  },
  "referencePhoto": "base64_encoded_reference_image"
}
```

**Parameters**:
- `query` (string, required): Search query
- `candidate` (object, optional): Selected candidate from Phase 1
  - `id`, `name`, `summary`, `imageUrl`
- `referencePhoto` (string, optional): Base64-encoded reference image for photo verification
  - If provided: All scraped photos are verified (90%+ threshold)
  - If omitted: All scraped photos are returned (fallback to Phase 1 behavior)

**Response**:
```json
{
  "personId": "uuid-123",
  "basic_info": {
    "name": "Elon Musk",
    "occupation": "CEO",
    "location": "Austin, TX",
    "company": "Tesla"
  },
  "social_profiles": [
    {
      "platform": "twitter",
      "username": "elonmusk",
      "url": "https://twitter.com/elonmusk",
      "followers": 150000000,
      "verified": true
    }
  ],
  "photos": [
    {
      "url": "https://supabase.io/storage/v1/object/public/photo_1.jpg",
      "source": "instagram",
      "verified": true,
      "similarity": 96.5,
      "caption": "At Tesla factory"
    },
    {
      "url": "https://supabase.io/storage/v1/object/public/photo_2.jpg",
      "source": "twitter",
      "verified": true,
      "similarity": 94.2,
      "caption": "SpaceX launch"
    }
  ],
  "public_records": {
    "relatives": ["Kimbal Musk"],
    "locations": ["Austin, TX", "San Francisco, CA"]
  },
  "answer": "Elon Musk is a tech entrepreneur...",
  "related_questions": ["What is his net worth?"]
}
```

---

## Implementation Details

### 1. Request Processing (routes/search.py)

```python
# Extract optional reference photo from request
reference_photo = data.get('referencePhoto')
if reference_photo:
    logger.info(f"Reference photo provided for face verification in aggregation")

# Pass to aggregation service
aggregated_data = aggregation_service.aggregate_person_data(
    query,
    websearch_result,
    apify_results,
    structured_info,
    pdl_data,
    reference_photo=reference_photo  # NEW PARAMETER
)
```

### 2. Photo Extraction (services/aggregation_service.py)

Photos are extracted from all scraped sources:
- **Instagram**: Latest posts (up to 10)
- **Twitter**: Tweet media (up to 10)
- **LinkedIn**: Profile pictures
- **OSINT sources**: Available images from TruePeopleSearch, FamilyTreeNow, etc.

**Total**: Typically 15–25 photos collected

### 3. Photo Verification (NEW in Phase 2)

**Method**: `_verify_photos_with_reference(photos, reference_photo)`

```python
def _verify_photos_with_reference(self, photos, reference_photo):
    """
    Phase 2: Verify photos against reference image using AWS Rekognition.
    
    - Decodes reference photo (base64)
    - Loops through all scraped photos
    - Compares each photo to reference using Rekognition
    - Keeps only photos with >= 90% similarity
    - Returns filtered list with 'verified' + 'similarity' fields
    """
```

**Logic**:
1. Decode reference photo (base64 → bytes)
2. For each scraped photo:
   - Download photo from URL
   - Call Rekognition `compare_faces()` with reference vs photo
   - Log similarity score
   - If similarity >= 90%: KEEP with `verified=true` + `similarity` score
   - If similarity < 90%: REJECT (not included in response)
3. Return filtered photo list

**Example Iteration**:
```
Photo 1 (Instagram): 96.5% → ✅ KEPT
Photo 2 (Instagram): 94.2% → ✅ KEPT
Photo 3 (Instagram): 15.0% → ❌ REJECTED (wrong person, meme)
Photo 4 (Twitter):   92.1% → ✅ KEPT
Photo 5 (Twitter):   8.3%  → ❌ REJECTED (not the target)
...
Result: 14/20 photos verified
```

### 4. Photo Proxying (Existing)

After verification, verified photos are proxied to Supabase:
- Downloads photo from source
- Stores in Supabase Storage
- Returns proxied URL (e.g., `supabase.io/storage/v1/.../photo_hash.jpg`)

### 5. Final Response

Only verified photos are included in the response with:
- `verified`: `true` (Phase 2 only)
- `similarity`: Rekognition match score (90–100)
- `url`: Proxied Supabase URL (to avoid external link rot)
- `source`: Platform (instagram, twitter, linkedin, etc.)
- `caption`: Photo caption/metadata

---

## Configuration

### Rekognition Credentials
Required in `.env`:
```bash
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-2
```

### Similarity Threshold
Currently hardcoded to **90%** in `_verify_photos_with_reference()`.  
Can be made configurable in future.

---

## Cost & Performance

### Rekognition API Calls
- **Phase 1** (Candidate Ranking): ~4 calls (comparing reference to 4 candidate images)
- **Phase 2** (Photo Verification): ~15–25 calls (comparing reference to all scraped photos)
- **Total per search**: ~20–30 API calls × $0.001 per call = **~$0.02–$0.03 per search**

### Response Time
- Rekognition verification: ~500ms per photo (sequential)
- 20 photos: ~10 seconds (can be parallelized in future with ThreadPoolExecutor)

---

## Files Modified

| File | Changes |
|------|---------|
| `routes/search.py` | Added `reference_photo` parameter extraction; pass to aggregation service |
| `services/aggregation_service.py` | Added `_verify_photos_with_reference()` method; call it during aggregation if reference photo provided |

---

## Files Created

| File | Purpose |
|------|---------|
| `PHASE2_PHOTO_VERIFICATION.md` | This documentation |

---

## Fallback Behavior

If photo verification fails at any step:
- **Rekognition unavailable**: Return all photos (no filtering)
- **Reference photo invalid**: Return all photos (no filtering)
- **Individual photo comparison fails**: Skip that photo (not included in response)

This ensures the endpoint always returns usable data even if verification services fail.

---

## Future Enhancements

1. **Parallelized Photo Verification**: Use ThreadPoolExecutor to compare multiple photos in parallel (faster response)
2. **Configurable Threshold**: Make 90% similarity threshold a parameter or environment variable
3. **Confidence Scoring**: Return similarity scores for all photos (not just keep/reject)
4. **Photo Clustering**: Group similar photos to avoid returning near-duplicates
5. **Face Detection**: Verify that photos contain exactly one face (additional validation)

---

## Usage Example (cURL)

```bash
# Step 1: Get candidates from Phase 1
curl -X POST http://localhost:5000/candidates/ranked \
  -F "query=Elon musk" \
  -F "file=@reference_photo.jpg"

# Response shows Candidate #1 with 95% match (id: "Elon Musk")

# Step 2: Deep search with photo verification (Phase 2)
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Elon musk",
    "candidate": {
      "id": "Elon Musk",
      "name": "Elon Musk",
      "summary": "CEO, Tesla & SpaceX"
    },
    "referencePhoto": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
  }'

# Response includes only verified photos (90%+ match)
```

---

## Testing

### Manual Test Scenario
1. Search for a famous person with reference photo (Phase 1)
2. Select top candidate
3. Call `/search` with same reference photo
4. Verify:
   - ✅ Photos are filtered (fewer than scraped total)
   - ✅ Each photo has `verified: true` and `similarity` score
   - ✅ Similarity scores are 90–100%
   - ✅ Response time is reasonable (~10–15 seconds for 20 photos)

### Edge Cases
- **No reference photo**: All photos returned (Phase 1 behavior preserved)
- **No photos from scraping**: Empty photo array (graceful fallback)
- **All photos rejected**: Empty photo array (no photos meet 90% threshold)
- **Rekognition timeout**: All photos returned (fallback to unverified)

---

## Notes

- Phase 2 is **completely optional**: Omitting `referencePhoto` falls back to Phase 1 behavior
- Reference photo must be in **base64** format (same as Phase 1)
- Photo verification happens **after scraping & deduplication**, before proxying
- All fields in `photos` objects are preserved; only `verified` and `similarity` are added
- URLs in final response point to **Supabase Storage** (proxied), not original sources

