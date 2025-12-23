# Phase 1 – Candidate Finding & Face Re-Ranking

Scope: Add a separate endpoint that fetches candidates and optionally re-ranks them with AWS Rekognition using a user-provided reference photo. The existing `/candidates` endpoint is untouched.

## Endpoints

### POST `/candidates` (existing, unchanged)
- Fetch candidates via existing pipeline (PDL/SerpAPI logic) and return as before.

### POST `/candidates/ranked` (new)
**Request**: `multipart/form-data`
- `query` (form-data, text): Search query (e.g., "Elon musk, San Francisco")
- `file` (form-data, file, optional): Reference image file (JPG, PNG, WEBP, etc.)
- Optional refinement params (form-data, text): `age`, `location`, `school`, `company`, `social`

**Example curl**:
```bash
curl -X POST "http://localhost:5000/candidates/ranked" \
  -F "query=Elon musk, San Francisco" \
  -F "file=@/path/to/reference_photo.jpg"
```

**Behavior**:
1. Fetch candidates via PDL (if available) or SerpAPI.
2. Deduplicate non-PDL candidates using LLM.
3. Hydrate images for top 5 candidates via SerpAPI image search (all candidates, not just PDL).
4. If `file` provided:
   - Save to temporary file
   - Normalize image to JPEG (handles WEBP, PNG, HEIC, oversized images)
   - Compare each candidate's image with reference photo via AWS Rekognition
   - Set `similarityScore` (0–100)
   - Sort by score (descending)
   - Assign `rank`
5. If no file: return candidates with `similarityScore = 0` and rank by order.
6. Always clean up temporary file before returning response.

**Response** (example):
```json
{
  "query": "Elon musk, San Francisco",
  "candidates": [
    {
      "id": "Elon Musk",
      "name": "Elon Musk",
      "description": "Businessman and entrepreneur known for Tesla, SpaceX, X, and xAI",
      "imageUrl": "https://...",
      "similarityScore": 89.5,
      "rank": 1
    },
    {
      "id": "candidate-2",
      "name": "Some Other Person",
      "description": "...",
      "imageUrl": null,
      "similarityScore": 0.0,
      "rank": 2
    }
  ]
}
```

## Technical Details

### Image Processing
- **Source** (reference file): Uploaded image → saved to temp file → read as bytes
- **Target** (candidate): Fetched via SerpAPI `fetch_image_url()` → downloaded → converted to bytes
- **Normalization** (both source & target):
  - Detect format (JPEG, PNG, WEBP, HEIC, etc.)
  - Convert to RGB (strip alpha channel)
  - Resize if > 4096px on either side
  - Encode as JPEG (quality 90)
  - Further downscale if > 5MB
  - Pass normalized bytes to Rekognition

### Image Hydration (SerpAPI)
- Applies to top 5 candidates (to save quota/time)
- Uses `serpapi_service.fetch_image_url(name + company)` to find profile pictures
- Logs success/failure for each candidate
- Falls back gracefully if no image found

### Deduplication (LLM)
- Only runs for non-PDL candidates (SerpAPI results)
- Uses OpenAI LLM to merge duplicate entries
- **Preserves all fields**, especially `imageUrl`
- Returns deduplicated list

### Rekognition Comparison
- Uses AWS Rekognition `compare_faces` API
- SimilarityThreshold: 70
- Returns best match similarity score (0–100)
- Handles errors gracefully (score = 0.0 on failure)

## Files
- `routes/candidates.py`: 
  - Original `POST /candidates` unchanged
  - New `POST /candidates/ranked` with form-data handling, temp file cleanup, image hydration for all candidates, Rekognition reranking
- `services/rekognition_service.py`: 
  - Thin wrapper around AWS Rekognition
  - `compare_faces_bytes(source_bytes, target_url)`: Normalizes both images, calls Rekognition, returns similarity score
  - `_normalize_image_bytes(data)`: Converts any image format to JPEG
  - `_download_image(url)`: Fetches target image with proper headers
  - Safe no-op if boto3 or AWS creds missing
- `services/websearch_service.py`:
  - Updated `deduplicate_candidates()` prompt to explicitly preserve `imageUrl` field

## Configuration
- **SerpAPI**: `SERPAPI_KEY` (existing)
- **Rekognition**: 
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_REGION` (default `us-east-2`)
- **Dependencies**: 
  - `boto3` (AWS SDK)
  - `Pillow` (image processing)

## Usage (Postman)
1. URL: `POST http://localhost:5000/candidates/ranked`
2. Body: `form-data`
   - Key `query` (text): your search query
   - Key `file` (file): select image file
   - Optional: `age`, `location`, `school`, `company`, `social` (text)
3. Click **Send**

## Notes
- Existing `/search` flow is untouched.
- Original `/candidates` endpoint is untouched.
- Errors in Rekognition or bad images degrade gracefully (scores stay 0, candidates still returned).
- Candidate IDs are enforced for stability; ranks are recomputed after scoring.
- Temporary files are cleaned up in `finally` block, even on error.
- Image hydration runs for all candidates (PDL + SerpAPI), not just PDL.

