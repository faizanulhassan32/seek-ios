# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a person-search intelligence platform (Deepsearch-style) that aggregates information about individuals from multiple sources including OpenAI websearch, Apify scrapers (Instagram, X, LinkedIn), and other data sources. The platform consists of a SwiftUI frontend and Flask backend with Supabase for database and auth.

**Tech Stack:**
- Frontend: SwiftUI (iOS 17+)
- Backend: Flask (Python 3.11+)
- Database: Supabase (PostgreSQL)
- Deployment: Render
- Data Sources: OpenAI (web search + chat), Apify (social scraping), Google Custom Search (optional image fallback)

## Monorepo Structure

```
root/
  personSearchFrontend/   # SwiftUI iOS app
  backend/                # Flask backend + Supabase integration
  documentation.md        # User guide
  README.md               # Setup instructions
  render.yaml             # Render deployment config
```

## Backend Architecture

The backend follows a service-oriented architecture:

```
backend/
  app.py                  # Flask app entry point with CORS
  setup_database.py       # Database initialization script
  run_migration.py        # Run database migrations
  routes/
    search.py             # POST /search - main search endpoint
    chat.py               # POST /chat - chat with AI about person (legacy)
    answer.py             # POST /answer/generate - AI biographical answer
    followup.py           # POST /followup - follow-up questions
  services/
    websearch_service.py  # OpenAI web search integration
    apify_service.py      # Social media scraping (Instagram/X/LinkedIn)
    aggregation_service.py # Merges data from multiple sources
    image_proxy_service.py # Supabase image caching/proxying
    answer_service.py     # AI answer generation
    followup_service.py   # Follow-up question answering
  db/
    supabase_client.py    # Supabase client wrapper
    schemas.sql           # PostgreSQL schema (users, persons, chats)
    migrations/           # Database migration files
      001_add_answer_columns.sql
  models/
    person.py             # Person data model
    chat.py               # Chat data model
  utils/
    logger.py             # Logging configuration
```

**Data Aggregation Pipeline:**
1. Receive query (name, email, phone, social handles)
2. Call OpenAI websearch API (gpt-5-mini with real-time web access)
3. Extract structured info from websearch results
4. Identify social media handles from query/results
5. Trigger Apify scrapers in parallel (Instagram/X/LinkedIn)
6. Merge and deduplicate data from all sources
7. **Image Proxy & Hybrid Fallback:**
   - Try to proxy images through Supabase Storage (handles CORS, hotlink protection, expiration)
   - Retry failed downloads with exponential backoff (3 attempts)
   - Filter out photos where proxy fails (429 rate limit, 404, timeouts)
   - If NO photos remain after filtering, trigger Google Custom Search API fallback
   - Google returns 5 validated image URLs
8. Store results in Supabase
9. Return structured schema

**Image Handling Architecture:**
- **Primary Source**: Wikimedia, SpaceX, IMDb, social media platforms
- **Proxy Service** (`image_proxy_service.py`):
  - Downloads images with User-Agent and Referer headers to bypass bot detection
  - Caches in Supabase Storage bucket `person_images/cache/`
  - Returns public Supabase URL (permanent, no CORS issues)
  - Retry logic: 3 attempts with exponential backoff for rate limits
  - Returns `None` for failed downloads (404, 403, timeout)
- **Aggregation Service** (`aggregation_service.py`):
  - Collects all image URLs (photos + profile pics)
  - Proxies them in parallel (max 10 workers)
  - **Filters out** photos where proxy returned `None` (broken URLs removed)
  - Keeps social profiles even if profile_pic fails (sets to `None`)
- **Search Route** (`search.py`):
  - If photos array is empty after filtering → triggers Google Images API
  - Google API validates each URL with HEAD request before returning
  - Returns up to 5 working image URLs
- **Frontend** (`SafeImage` in `PersonDetailView.swift`):
  - Custom URLSession-based image loader
  - Adds User-Agent, empty Referer, Accept headers
  - 20-second timeout for slow images
  - Retry logic: 3 attempts with 0.5s/1.0s/1.5s delays
  - Detailed error logging for debugging

**API Endpoints:**

- `GET /health` - Health check endpoint
- `POST /search` - Search for person information
- `POST /chat` - Chat about a person using their search data (legacy)
- `POST /answer/generate` - Generate AI biographical answer for a person
- `GET /answer/<person_id>` - Get existing answer without regenerating
- `POST /followup` - Ask follow-up questions about a person

## Frontend Architecture (SwiftUI)

**CRITICAL:** Do NOT restructure the existing `personSearchFrontend/` folder. Add files only where appropriate.

Actual structure inside `personSearchFrontend/personSearchFrontend/`:

```
Views/
  SearchView.swift
  PersonDetailView.swift
  ChatView.swift
  OnboardingView.swift
  LoadingView.swift
  Components/              # Reusable UI components
    AnswerSection.swift
    SourcesSection.swift
    RelatedSection.swift
    FollowUpCardView.swift
    FollowUpInputBar.swift
    PersonDetailNavBar.swift
    PersonVerificationView.swift

ViewModels/
  SearchViewModel.swift
  ChatViewModel.swift
  OnboardingViewModel.swift

Networking/
  APIClient.swift          # Base HTTP client with error handling
  SearchAPI.swift          # Search endpoint wrapper
  ChatAPI.swift            # Chat endpoint wrapper
  AnswerAPI.swift          # Answer generation endpoint
  FollowUpAPI.swift        # Follow-up questions endpoint

Models/
  Person.swift
  SearchResult.swift
  Message.swift
  Source.swift
  FollowUpCard.swift
```

## Development Commands

### Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Initialize database (run SQL in Supabase SQL Editor)
python setup_database.py

# Run development server
python app.py
```

### Backend Testing
```bash
cd backend
source venv/bin/activate

# Test health endpoint
curl http://localhost:5000/health

# Test search endpoint
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "elon musk"}'
```

### Frontend Setup
```bash
# Open in Xcode
open personSearchFrontend/personSearchFrontend.xcodeproj

# Update backend URL in Networking/APIClient.swift
# For local dev: "http://localhost:5000"
# For production: "https://your-app.onrender.com"
```

**Xcode Commands:**
- `Cmd+R` - Build and run
- `Cmd+B` - Build only
- `Cmd+U` - Run tests
- `Cmd+.` - Stop running app

## Database Setup

The database schema (`backend/db/schemas.sql`) defines three tables:
- `users` - For future authentication (currently unused)
- `persons` - Stores search results with JSONB fields (includes `answer`, `related_questions`, `answer_generated_at` columns)
- `chats` - Stores conversation history linked to persons

**Setup process:**
1. Create Supabase project at supabase.com
2. Copy connection details to `.env`
3. Run `python setup_database.py` OR manually execute `schemas.sql` in Supabase SQL Editor
4. Run migrations: `python run_migration.py` (applies `db/migrations/*.sql` files)
5. Verify tables created: users, persons, chats
6. Create Supabase Storage bucket: `person_images` (public access, no RLS)

## Code Generation Rules

1. **Always output functional, runnable code.** No pseudo-code, no placeholders like `<something>`. If something is unknown, make a strong assumption and continue.

2. **Cross-platform consistency.** Backend models ↔ Swift structs ↔ Supabase schemas must always match exactly. Pay special attention to JSON key naming (snake_case in Python/DB, camelCase in Swift).

3. **Preserve existing structure.** Never restructure the SwiftUI folder - only add files where appropriate.

4. **Service abstraction.** All external API calls must be abstracted in service layers:
   - Backend: `services/` directory
   - Frontend: `Networking/` directory

5. **Error handling.** Both frontend and backend have comprehensive error handling - maintain this pattern.

6. **Future extensibility.** Design for expansion - more data sources will be added.

## Chat System Architecture

The chat system injects search data as context:
- Backend retrieves person data from Supabase using `personId`
- Structured data is injected into system prompt
- OpenAI generates contextual responses
- Conversation history stored in `chats` table with JSONB messages array
- Supports follow-up queries about specific data aspects

## Environment Variables

**Backend** (`.env` in `backend/` directory):
```bash
OPENAI_API_KEY=sk-...           # Required: OpenAI API key
APIFY_API_KEY=apify_...         # Required: Apify API key
SUPABASE_URL=https://...        # Required: Supabase project URL
SUPABASE_KEY=eyJ...             # Required: Supabase anon key
GOOGLE_API_KEY=AIza...          # Optional: Google Custom Search API key
GOOGLE_CX=...                   # Optional: Google Custom Search Engine ID
FLASK_ENV=development           # development or production
PORT=5000                       # Local: 5000, Render: 10000
```

**Frontend:**
- Backend URL configured in `APIClient.swift` (line 41-47)
- Uses `#if DEBUG` to switch between local and production URLs

## Troubleshooting

### Image Loading Issues

**Symptom:** Gray rectangles with photo icon in frontend

**Common Causes & Fixes:**

1. **Image proxy failing** (most common):
   - Check backend logs for "Failed to download image" warnings
   - Look for HTTP 429 (rate limit), 404 (not found), or timeout errors
   - If all proxies fail, Google Images fallback should trigger automatically
   - Verify Supabase Storage bucket `person_images` exists and is public

2. **Google API not configured**:
   - Check `.env` has `GOOGLE_API_KEY` and `GOOGLE_CX` set
   - Test Google Custom Search API: `curl "https://www.googleapis.com/customsearch/v1?q=test&cx=YOUR_CX&key=YOUR_KEY&searchType=image"`
   - Backend logs should show "Fetched and validated X Google images"

3. **Frontend loading errors**:
   - Check Xcode console for "❌ Image load error" messages
   - Look for network errors, timeouts, or HTTP status codes
   - Verify image URLs are valid (not null or empty)
   - Try opening image URL in browser to test accessibility

4. **Supabase Storage not set up**:
   - Log into Supabase dashboard → Storage
   - Create bucket named `person_images` if missing
   - Set to public access, disable RLS (Row Level Security)
   - Test public URL access

**Debug Commands:**

```bash
# Backend: Check if images are being proxied
tail -f backend/logs/app.log | grep "image"

# Frontend: Watch for image errors in Xcode console
# Look for lines starting with "❌ Image load"

# Test Google Images API directly
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test person"}' | jq '.photos'
```

**Expected Behavior:**
1. ✅ Proxy tries direct URLs (Wikimedia, SpaceX, etc.)
2. ❌ Some fail (429/404) → filtered out
3. ✅ Google fallback triggers if photos array empty
4. ✅ Frontend displays Google images successfully

## Deployment (Render)

The project includes `render.yaml` for automatic deployment:

```bash
# Deploy to Render
1. Connect GitHub repo to Render
2. Render auto-detects render.yaml
3. Set environment variables in Render dashboard
4. Deploy starts automatically

# Manual deployment
render-cli deploy
```

**Important:** Render uses Python 3.11.7 and runs `gunicorn app:app` in production.
