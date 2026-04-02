import trafilatura
from typing import Optional

def scrape_article(url: str) -> Optional[str]:
    """
    Scrape the main text content from a given URL using Trafilatura.
    Returns the text content or None if extraction fails.
    """
    import os
    import re
    from urllib.parse import urlparse

    log_file = "output/scraping.log"
    content_dir = "output/scraped_content"
    os.makedirs(content_dir, exist_ok=True)

    try:
        domain = urlparse(url).netloc.replace(".", "_")
        safe_url = re.sub(r'[^a-zA-Z0-9]', '_', url)[-50:]
        content_path = os.path.join(content_dir, f"{domain}_{safe_url}.txt")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"DEBUG: Scraping URL: {url}\n")
        
        # Use a user agent to avoid being blocked by some sites
        downloaded = trafilatura.fetch_url(url)
        
        if downloaded:
            # Try extraction with more lenient settings
            text = trafilatura.extract(downloaded, include_comments=False, no_fallback=False)
            
            if text:
                # Save the content for manual inspection
                with open(content_path, "w", encoding="utf-8") as f:
                    f.write(f"URL: {url}\n\n")
                    f.write(text)

                if len(text) >= 100:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"DEBUG: Successfully scraped {len(text)} chars from {url}. Saved to {content_path}\n")
                    return text
                else:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"DEBUG: Scraped text too short ({len(text)} chars) from {url}\n")
            else:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"DEBUG: Trafilatura extracted empty text from {url}\n")
        else:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"DEBUG: Trafilatura failed to download {url}\n")
    except Exception as e:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"Error scraping {url}: {e}\n")
    return None
