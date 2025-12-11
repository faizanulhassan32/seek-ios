# Architecture Deep Dive: Under the Hood

This document explains exactly how the Person Search App works, layer by layer.

## 1. The Big Picture

The app follows a classic **Client-Server** architecture.
- **Client (Frontend)**: The iOS App. It handles user interaction.
- **Server (Backend)**: The Python API. It handles logic, data fetching, and storage.
- **Database**: Supabase. It stores persistent data.

---

## 2. The Frontend (iOS App)
**Tech Stack**: Swift, SwiftUI

The iOS app is designed to be "dumb" but beautiful. It doesn't know how to scrape Instagram or talk to OpenAI. Its only job is to:
1.  **Ask** the backend for data.
2.  **Wait** (show loading animations).
3.  **Show** the data when it arrives.

### Key Components:
- **`SearchViewModel`**: The brain of the frontend. It manages the state (e.g., "Is it loading?", "Do we have results?"). It talks to the backend API.
- **`SearchView`**: The main screen. It watches the `SearchViewModel` and updates the UI automatically.
- **`PersonSelectionView`**: The screen where you pick the right person from a list of candidates.

---

## 3. The Backend (Python API)
**Tech Stack**: Python, Flask, Gunicorn
**Hosting**: Render

This is where the magic happens. The backend is organized into **Services**. Each service has a specific specialty.

### The "Manager": `search.py` (Route)
Think of this as the project manager. When a request comes in (`/search`), it coordinates the team:
1.  **Check Cache**: "Hey Database, do we already know this person?"
    - *Yes?* Return it immediately (0.1s).
    - *No?* Start a new investigation (30s).

### The "Specialists" (Services)

#### A. `WebSearchService` (The Researcher)
- **Tool**: OpenAI (GPT-4o-mini).
- **Job**: It performs a broad search using OpenAI's browsing capabilities.
- **Output**: A summary text and a list of "Identifiers" (social media links found in the text).

#### B. `ApifyService` (The Scraper)
- **Tool**: Apify Actors.
- **Job**: Once we have links (e.g., `twitter.com/elonmusk`), this service sends specific robots to go there.
- **Speed Trick**: It uses **Parallel Processing**. It launches the Instagram robot, Twitter robot, and LinkedIn robot *at the same time*. It doesn't wait for one to finish before starting the next.

#### C. `SerpApiService` (The Headhunter)
- **Tool**: Google Search API.
- **Job**: Used only at the start to find the list of candidates ("Did you mean Elon Musk the CEO or the Doctor?").

#### D. `AggregationService` (The Editor)
- **Job**: It takes the messy pile of data from everyone (OpenAI summary, 50 tweets, 10 Instagram photos) and cleans it up.
- **Image Proxying**: It downloads images from Instagram/Twitter and re-uploads them to our own **Supabase Storage**.
    - *Why?* Because Instagram image links "expire" after a few hours. If we don't save them, the app would show broken images tomorrow.

---

## 4. The Database (Supabase)
**Tech Stack**: PostgreSQL

We use Supabase for two things:
1.  **Data (`persons` table)**: Stores the final JSON profile.
    - We use a "Cache Key" (e.g., `elon musk::ceo of tesla`) to find people quickly.
2.  **Images (Storage Bucket)**: Stores the profile pictures and photos we downloaded.

---

## 5. The Data Flow (A Complete Journey)

1.  **User** types "Jensen Huang" in iOS App.
2.  **App** calls Backend: `GET /candidates?query=Jensen Huang`.
3.  **Backend** asks **SerpApi** -> Returns list of 10 Jensens.
4.  **User** taps "Jensen Huang (CEO of Nvidia)".
5.  **App** calls Backend: `POST /search` with the specific person's details.
6.  **Backend** checks **Supabase**: "Do we have him?" -> *No.*
7.  **Backend** asks **OpenAI**: "Search for Jensen Huang Nvidia."
    - *Result*: "He is the CEO... Twitter: @nvidia, LinkedIn: /in/jensen..."
8.  **Backend** sees Twitter and LinkedIn links.
9.  **Backend** fires **Apify**:
    - Robot A -> Scrapes Twitter.
    - Robot B -> Scrapes LinkedIn.
10. **Backend** waits for both to finish.
11. **Backend** (Aggregation) combines everything.
12. **Backend** downloads images and saves them to **Supabase Storage**.
13. **Backend** saves the full profile to **Supabase Database**.
14. **Backend** sends the profile to **App**.
15. **App** displays the profile.

Next time someone searches for "Jensen Huang", we skip steps 7-13 and just return the saved data instantly!
