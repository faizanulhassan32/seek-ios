# Phase 1 – Candidate Finding & Face Re-Ranking

Scope: Add a separate endpoint that fetches candidates and optionally re-ranks them with AWS Rekognition using a user-provided reference photo. The existing `/candidates` endpoint is untouched.

## Endpoints

### POST `/candidates` (existing, unchanged)
- Fetch candidates via existing pipeline (PDL/SerpAPI logic) and return as before.

### POST `/candidates/ranked` (new)
Request:
```json
{
  "query": "Faizan ul hassan",
  "referencePhoto": "<base64 image>"  // optional
}
```
Behavior:
- Fetch top candidates from SerpAPI (capped at 5 for cost/time).
- If `referencePhoto` provided: decode base64 → compare with each candidate image via Rekognition → set `similarityScore` → sort desc → assign `rank`.
- If no `referencePhoto`: return candidates with `similarityScore = 0` and rank by original order.
- If invalid photo or errors: gracefully fall back to unranked response.

Response (example):
```json
{
  "query": "Faizan ul hassan",
  "candidates": [
    { "id": "c1", "name": "Faizan ul hassan", "summary": "Software Engineer", "imageUrl": "...", "similarityScore": 95.4, "rank": 1 },
    { "id": "c2", "rank": 2, "similarityScore": 12.0 },
    { "id": "c3", "rank": 3, "similarityScore": 8.5 }
  ]
}
```

## Files
- `routes/candidates.py`: adds POST `/candidates/ranked`; keeps original `/candidates` unchanged.
- `services/rekognition_service.py`: thin Rekognition wrapper (`compare_faces_bytes`), safe no-op if boto3/creds missing.

## Config
- SerpAPI: `SERPAPI_KEY` (existing).
- Rekognition: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (default `us-east-1`).
- Dependency: `boto3`.

## Notes
- Existing `/search` flow is untouched.
- Errors in Rekognition or bad images degrade gracefully (scores stay 0, candidates still returned).
- Candidate IDs are enforced for stability; ranks are recomputed after scoring.
