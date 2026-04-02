import requests
import time
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"

def get_top_story_ids(limit: int = 10) -> List[int]:
    """Fetch the top N story IDs from Hacker News."""
    try:
        response = requests.get(f"{HN_API_BASE}/topstories.json")
        response.raise_for_status()
        story_ids = response.json()
        return story_ids[:limit]
    except requests.RequestException as e:
        print(f"Error fetching top stories: {e}")
        return []

def get_story_details(story_id: int) -> Optional[Dict]:
    """Fetch details for a specific story ID."""
    try:
        response = requests.get(f"{HN_API_BASE}/item/{story_id}.json")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching story details for ID {story_id}: {e}")
        return None

def fetch_top_stories(limit: int = 10) -> List[Dict]:
    """Fetch top N stories with their details."""
    ids = get_top_story_ids(limit)
    stories = []
    for sid in ids:
        details = get_story_details(sid)
        if details and details.get('url'): # Only include stories with URLs
            stories.append(details)
    return stories

def fetch_stories_by_date(date_str: str, limit: int = 10) -> List[Dict]:
    """
    Fetch top stories for a specific date from the HN front page snapshots.
    URL format: https://news.ycombinator.com/front?day=YYYY-MM-DD
    """
    url = f"https://news.ycombinator.com/front?day={date_str}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            stories = []
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # HN structure: <span class="titleline"><a href="url">title</a></span>
            items = soup.find_all('span', class_='titleline')
            
            for item in items[:limit]:
                link = item.find('a')
                if link and link.get('href'):
                    href = link.get('href')
                    if href.startswith('item?id='):
                        story_id = href.split('=')[1]
                        details = get_story_details(int(story_id))
                        if details and details.get('url'):
                            stories.append(details)
                    else:
                        stories.append({
                            'title': link.text,
                            'url': href
                        })
            
            if stories:
                print(f"Scraped {len(stories)} stories for {date_str}")
                return stories
            else:
                print(f"No stories found on HN front page for {date_str} (Attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue

        except Exception as e:
            print(f"Error scraping stories for {date_str} (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1)) # Simple exponential backoff
                continue
    
    return []
