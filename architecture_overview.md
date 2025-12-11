# How It Works: A Simple Overview

Imagine this app as a **digital detective agency**. You are the client, the iOS app is the front desk, and the Python backend is the team of detectives.

## 1. The Front Desk (iOS App)
This is what you hold in your hand.
- **Role**: It takes your request ("Find Seungho Choi") and shows you the results.
- **Technology**: Built with **SwiftUI** (Apple's language for apps).
- **Key Job**: It doesn't do the heavy lifting. It just sends orders to the "Detectives" and displays what they find nicely.

## 2. The Detectives (Python Backend)
This is the brain of the operation, running on a server (Render).
- **Role**: It does all the searching, reading, and summarizing.
- **Technology**: Built with **Python** (Flask).

## 3. The Investigation Process (Step-by-Step)

Here is what happens when you search for someone:

### Step 1: The Initial Look (Candidate Search)
1.  You type a name (e.g., "Elon Musk").
2.  The **Backend** asks **Google** (via **SerpApi**): "Who are the most famous people with this name?"
3.  It returns a list (e.g., Elon Musk the CEO, Elon Musk the Doctor).
4.  You pick the right one.

### Step 2: The Deep Dive (Deep Search)
Once you select a person, the real work begins. The Backend acts like a coordinator:

1.  **General Web Search**:
    - It asks **OpenAI (ChatGPT)** to browse the internet and write a summary of the person (Job, Location, Education).
    - It also finds their social media links (Instagram, Twitter, LinkedIn).

2.  **Social Media Raid (Parallel Processing)**:
    - If OpenAI finds social links, the Backend hires "specialists" (**Apify Actors**) to go to those specific sites.
    - One specialist goes to **Instagram** to get photos.
    - Another goes to **Twitter** to get tweets.
    - Another goes to **LinkedIn** for job history.
    - *They all do this at the same time (in parallel) to be fast.*

3.  **Fallback Plan**:
    - If OpenAI *missed* a social link (e.g., couldn't find Instagram), the Backend runs a specific "Google Search" just for that missing link to try and find it.

### Step 3: The Report (Aggregation)
1.  The Backend gathers all the notes:
    - Summary from OpenAI.
    - Photos from Instagram.
    - Tweets from Twitter.
    - Job info from LinkedIn.
2.  It uses **OpenAI** again to combine this into one clean, final profile.
3.  It **saves** this profile in a database (**Supabase**) so if you search for them again, it's instant (Caching).

### Step 4: Delivery
- The Backend sends this final JSON "Report" back to the **iOS App**.
- The App formats it into the beautiful profile screen you see.

---

## Summary of Tools Used
- **SerpApi**: Used to find the list of people (Candidates).
- **OpenAI**: Used to read websites, summarize text, and organize data.
- **Apify**: Used to scrape specific social media apps (Instagram, Twitter, etc.).
- **Supabase**: The filing cabinet (Database) where reports are stored.
