# Person Search App - Setup Guide

This guide will walk you through setting up the Person Search application from scratch. It is designed for beginners.

## Prerequisites

- A computer (Mac preferred for iOS development)
- Basic familiarity with the terminal/command line
- Accounts for the services listed below

---

## 1. Create Accounts and Get API Keys

You will need several API keys to make the app work. Save these keys in a safe place (like a text file) as you generate them.

### A. SerpApi (Google Search Results)
1.  Go to [serpapi.com](https://serpapi.com/).
2.  Sign up for an account.
3.  Go to your dashboard/account settings to find your **Private API Key**.
4.  Save this as `SERPAPI_KEY`.

### B. Apify (Social Media Scraping)
1.  Go to [apify.com](https://apify.com/).
2.  Sign up for an account.
3.  Go to **Settings > Integrations**.
4.  Copy your **Personal API Token**.
5.  Save this as `APIFY_API_KEY`.

### B.1. Rent Apify Actors
The app uses specific "Actors" (scripts) to scrape data. Some of these are paid or require a subscription (rental) to work.
1.  Go to [Apify Store](https://apify.com/store).
2.  Search for and **Rent/Subscribe** to the following actors (even the free trial if available):
    - `apify/instagram-profile-scraper` (Instagram)
    - `web.harvester/twitter-scraper` (Twitter/X)
    - `apimaestro/linkedin-profile-posts` (LinkedIn)
    - `clockworks/tiktok-profile-scraper` (TikTok)
    - `lazyscraper/facebook-profile-scraper` (Facebook)
    - `pratikdani/youtube-profile-scraper` (YouTube)
    - `apify/google-search-scraper` (Fallback Search)
    - `apify/web-scraper` (Generic Web)
3.  Ensure you have a payment method attached if the free trial expires.

### C. OpenAI (AI Intelligence)
1.  Go to [platform.openai.com](https://platform.openai.com/).
2.  Sign up or log in.
3.  Go to **API Keys** in the sidebar.
4.  Click **Create new secret key**.
5.  Copy the key immediately (you won't see it again).
6.  Save this as `OPENAI_API_KEY`.

---

## 2. Google Images Setup

This is required to fetch images for the people you search for.

### A. Get Google API Key
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project (e.g., "Person Search App").
3.  In the search bar at the top, type **"Custom Search API"** and select it.
4.  Click **Enable**.
5.  Go to **Credentials** (in the sidebar).
6.  Click **Create Credentials** > **API Key**.
7.  Copy the key.
8.  Save this as `GOOGLE_API_KEY`.

### B. Get Search Engine ID (CX)
1.  Go to [Programmable Search Engine](https://cse.google.com/cse/all).
2.  Click **Add**.
3.  **Name**: "Person Search".
4.  **What to search**: Select **"Search the entire web"**.
5.  **Image Search**: Turn **ON** "Image search".
6.  **SafeSearch**: Select "Filter using SafeSearch".
7.  Click **Create**.
8.  On the next page (or in the "Overview" tab), copy the **Search engine ID** (it looks like `0123456789:abcdefghijk`).
9.  Save this as `GOOGLE_CX`.

---

## 3. GitHub Setup

You need to get the code onto your computer.

1.  **Install Git** (if not already installed).
    - Mac: Open Terminal and type `git`. If not installed, it will prompt you to install Xcode Command Line Tools.
2.  **Clone the Repository**:
    - Open Terminal.
    - Navigate to where you want the project (e.g., `cd Documents`).
    - Run the command:
      ```bash
      git clone <YOUR_REPOSITORY_URL>
      ```
    - Enter the folder:
      ```bash
      cd personSearch
      ```

---

## 4. Supabase Setup (Database)

1.  Go to [supabase.com](https://supabase.com/) and sign up.
2.  Click **New Project**.
3.  Give it a name and a strong password. Choose a region near you.
4.  Wait for the database to set up.

### A. Get Credentials
1.  Go to **Project Settings** (gear icon) > **API**.
2.  Copy the **Project URL**. Save as `SUPABASE_URL`.
3.  Copy the **anon public** key. Save as `SUPABASE_KEY`.
4.  Copy the **service_role** key (reveal it first). Save as `SUPABASE_SERVICE_ROLE_KEY`.

### B. Setup Database Schema
1.  In the Supabase Dashboard, go to the **SQL Editor** (icon with two brackets `[ ]` on the left).
2.  Click **New Query**.
3.  Copy the contents of the file `backend/db/schemas.sql` from the project code.
    - *If you can't find it, ask the developer for the SQL schema script.*
4.  Paste the SQL into the editor.
5.  Click **Run**.
6.  You should see "Success" in the results.

---

## 5. Render Setup (Backend Hosting)

We will use Render to host the Python backend.

1.  Go to [render.com](https://render.com/) and sign up.
2.  Click **New +** and select **Blueprint**.
3.  Connect your GitHub account and select the `personSearch` repository.
4.  Render will automatically detect the `render.yaml` file.
5.  **Environment Variables**: You will be prompted to enter the keys you collected earlier. Fill them in:
    - `OPENAI_API_KEY`
    - `SUPABASE_URL`
    - `SUPABASE_KEY`
    - `SUPABASE_SERVICE_ROLE_KEY`
    - `GOOGLE_API_KEY`
    - `GOOGLE_CX`
    - `APIFY_API_KEY`
    - `SERPAPI_KEY`
6.  Click **Apply**. Render will start building and deploying your app.
7.  Once finished, you will get a URL (e.g., `https://person-search.onrender.com`). Save this URL.

---

## 6. Apple Developer Setup

Required to publish the iOS app.

1.  Go to [developer.apple.com](https://developer.apple.com/).
2.  Click **Account** and sign in with your Apple ID.
3.  Join the **Apple Developer Program** (costs ~$99/year).
4.  Once enrolled, go to **Certificates, Identifiers & Profiles**.
5.  **Identifiers**: Create a new App ID.
    - Select **App IDs**.
    - Select **App**.
    - Description: "Person Search".
    - Bundle ID: `com.yourname.personSearch` (must be unique).
    - Enable **In-App Purchase** capability.
    - Register.

---

## 7. Superwall Setup (Paywall)

1.  Go to [superwall.com](https://superwall.com/) and sign up.
2.  Create a new project.
3.  Go to **Settings > Keys**.
4.  Copy the **Public API Key** (starts with `pk_`).
5.  **Add to iOS App**:
    - Open the project in Xcode (`personSearchFrontend/personSearchFrontend.xcodeproj`).
    - Open the file `personSearchFrontend/Config.swift`.
    - Replace the `superwallAPIKey` value with your new key:
      ```swift
      static let superwallAPIKey = "pk_YOUR_NEW_KEY_HERE"
      ```

---

## Final Steps

1.  **Update Backend URL in iOS App**:
    - In Xcode, find `Config.swift` (or where the base URL is defined).
    - Update the `baseURL` to your Render URL (from Step 5).
2.  **Build and Run**:
    - Select your iPhone simulator or device.
    - Click the Play button in Xcode.

You are now ready to go!
