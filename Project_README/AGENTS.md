# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: Flask app entry `app.py`; `routes/` for search/chat endpoints; `services/` for integrations (websearch, Apify, aggregation); `db/` for Supabase client and schemas; `models/` for person/chat data; `utils/logger.py` for logging. Add new endpoints under `routes/` and keep business logic in `services/`.
- `personSearchFrontend/`: SwiftUI app with `Models/`, `ViewModels/`, `Networking/` (APIClient, SearchAPI, ChatAPI), `Views/`, and Xcode project/workspaces plus UI/Unit test targets. Preserve the existing folder layout; add new screens under `Views/` with matching view models.

## Build, Test, and Development Commands
- Backend setup: `cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- Run backend: `cd backend && source venv/bin/activate && python app.py` (uses `.env`).
- iOS app: open `personSearchFrontend/personSearchFrontend.xcodeproj` in Xcode; run with `Cmd+R` against a simulator. Update the base URL in `personSearchFrontend/Networking/APIClient.swift` for local vs. production.
- Tests: `xcodebuild test -scheme personSearchFrontend -destination 'platform=iOS Simulator,name=iPhone 15'`. Backend tests are not yet present; add `pytest` suites under `backend/tests/` when introducing new logic.

## Coding Style & Naming Conventions
- Python: PEP8 with 4-space indents; snake_case for functions/variables, PascalCase for classes. Keep routes thin and delegate to service layers with clear interfaces.
- Swift: follow Swift API Design Guidelines; camelCase for vars/functions, UpperCamelCase for types. Keep networking in `Networking/` and state in `ViewModels/`. Prefer dependency injection for API clients and mockable protocols for testing.

## Testing Guidelines
- Backend: when adding routes/services, write `pytest` cases (e.g., `backend/tests/test_search_route.py`) using `FlaskClient`; mock external calls (OpenAI, Apify, Supabase) to avoid slow/flaky tests.
- iOS: keep unit tests in `personSearchFrontendTests` and UI tests in `personSearchFrontendUITests`; name tests after the feature (`testSearchViewShowsResults`). Run `Cmd+U` in Xcode or the `xcodebuild test` command above. Target coverage on new logic for search and chat flows.

## Commit & Pull Request Guidelines
- Commit messages: concise, imperative, and optionally scoped (`backend: add aggregation validation`, `ios: improve chat view state`). Avoid bundling unrelated changes.
- PRs: include intent, key changes, and test evidence. Add screenshots for UI updates, sample API payloads for backend changes, and note any new env vars or migrations (`db/schemas.sql`). Link issues/tickets when available.

## Security & Configuration
- Never commit secrets. Use `backend/.env` (copy from `.env.example`) and keep keys out of Swift sources; read config via utilities. Validate required env vars on startup when possible.
- Guard external API calls with error handling and logging via `backend/utils/logger.py`; be mindful of rate limits and costs.
