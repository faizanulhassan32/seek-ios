# Person Search App

A Deepsearch-style intelligence platform for gathering and aggregating information about individuals from multiple sources including OpenAI websearch, Instagram, Twitter/X, and LinkedIn.

## Tech Stack

- **Frontend**: SwiftUI (iOS 17+)
- **Backend**: Flask (Python)
- **Database**: Supabase (PostgreSQL)
- **Deployment**: Render
- **Data Sources**: OpenAI, Apify

## Project Structure

```
personSearch/
├── backend/                    # Flask backend
│   ├── routes/                 # API endpoints
│   │   ├── search.py          # POST /search
│   │   └── chat.py            # POST /chat
│   ├── services/               # Business logic
│   │   ├── websearch_service.py
│   │   ├── apify_service.py
│   │   └── aggregation_service.py
│   ├── db/                     # Database
│   │   ├── supabase_client.py
│   │   └── schemas.sql
│   ├── models/                 # Data models
│   │   ├── person.py
│   │   └── chat.py
│   ├── utils/                  # Utilities
│   │   └── logger.py
│   ├── app.py                  # Flask app entry point
│   └── requirements.txt
│
└── personSearchFrontend/       # SwiftUI iOS app
    ├── Models/                 # Data models
    │   ├── Person.swift
    │   ├── Message.swift
    │   └── SearchResult.swift
    ├── Networking/             # API layer
    │   ├── APIClient.swift
    │   ├── SearchAPI.swift
    │   └── ChatAPI.swift
    ├── ViewModels/             # View models
    │   ├── SearchViewModel.swift
    │   └── ChatViewModel.swift
    └── Views/                  # UI views
        ├── SearchView.swift
        ├── PersonDetailView.swift
        └── ChatView.swift
```

## Setup Instructions

### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Create a `.env` file in the `backend/` directory:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   APIFY_API_KEY=your_apify_api_key_here
   SUPABASE_URL=your_supabase_url_here
   SUPABASE_KEY=your_supabase_anon_key_here
   FLASK_ENV=development
   PORT=5000
   ```

5. **Set up Supabase database**

   - Create a new project at [supabase.com](https://supabase.com)
   - Run the SQL from `db/schemas.sql` in the Supabase SQL editor
   - Copy your project URL and anon key to the `.env` file

6. **Run the backend**
   ```bash
   python app.py
   ```

   The backend will be available at `http://localhost:5000`

### Frontend Setup

1. **Open Xcode project**
   ```bash
   open personSearchFrontend/personSearchFrontend.xcodeproj
   ```

2. **Update backend URL**

   In `Networking/APIClient.swift`, update the backend URL if needed:
   ```swift
   private let baseURL: String = {
       #if DEBUG
       return "http://localhost:5000"  // For local development
       #else
       return "https://your-app-name.onrender.com"  // For production
       #endif
   }()
   ```

3. **Build and run**
   - Select a simulator or device
   - Press `Cmd+R` to build and run

## API Endpoints

### POST /search

Search for information about a person.

**Request:**
```json
{
  "query": "john doe"
}
```

**Response:**
```json
{
  "personId": "uuid",
  "basic_info": {
    "name": "John Doe",
    "age": 30,
    "location": "New York",
    "occupation": "Software Engineer"
  },
  "social_profiles": [
    {
      "platform": "instagram",
      "username": "johndoe",
      "followers": 1000
    }
  ],
  "photos": [...],
  "notable_mentions": [...],
  "raw_sources": [...]
}
```

### POST /chat

Chat with AI about a person.

**Request:**
```json
{
  "personId": "uuid",
  "messages": [
    {
      "role": "user",
      "content": "Tell me about this person's background"
    }
  ]
}
```

**Response:**
```json
{
  "reply": "Based on the available information...",
  "chatId": "uuid"
}
```

## Deployment

### Deploying to Render

1. **Create a Render account**
   - Go to [render.com](https://render.com) and sign up

2. **Create a new Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Or use "Deploy from Git URL"

3. **Configure the service**
   - **Name**: `your-app-name`
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

4. **Set environment variables**

   In the Render dashboard, go to Environment and add:
   ```
   OPENAI_API_KEY=your_key
   APIFY_API_KEY=your_key
   SUPABASE_URL=your_url
   SUPABASE_KEY=your_key
   FLASK_ENV=production
   PORT=10000
   ```

5. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your app
   - Your app will be available at `https://your-app-name.onrender.com`

6. **Update frontend**

   Update the production URL in `APIClient.swift` with your Render app URL:
   ```swift
   return "https://your-app-name.onrender.com"
   ```

## Features

### Search Functionality
- Search by name, email, username, phone, or any identifier
- Aggregates data from multiple sources:
  - OpenAI websearch
  - Instagram (via Apify)
  - Twitter/X (via Apify)
  - LinkedIn (via Apify)
- Displays structured information:
  - Basic info (name, age, location, occupation)
  - Social media profiles
  - Photos
  - Notable mentions

### Chat Functionality
- Context-aware AI conversations about searched individuals
- Maintains conversation history
- Supports follow-up queries
- Data stored in Supabase

## Development

### Running Tests

Backend:
```bash
cd backend
pytest
```

Frontend:
- Press `Cmd+U` in Xcode to run tests

### Adding New Data Sources

1. Create a new service in `backend/services/`
2. Implement data fetching logic
3. Update `aggregation_service.py` to include new data
4. Update the Person model if needed

## License

MIT

## Support

For issues and feature requests, please create an issue in the repository.
