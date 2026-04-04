import os
import sys
import time
import schedule
import argparse
import json
from datetime import datetime, timedelta
import logging
import shutil
import glob
import subprocess
from dotenv import load_dotenv

from app.hn_client import fetch_top_stories, fetch_stories_by_date
from app.scraper import scrape_article
from app.summarizer import summarize_article
from app.audio_generator import create_podcast_audio
from app.rss_generator import generate_rss

# Ensure stdout uses UTF-8 to avoid encoding errors on some systems (like Windows console)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf8', buffering=1)

# Change this to your public hosting URL
BASE_URL = os.getenv("PODCAST_BASE_URL", "https://your-domain.com/podcasts/")

# Configure logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/pipeline.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("hn_podcast")

load_dotenv()

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def job(target_date=None):
    if target_date is None:
        target_date = datetime.now()
    
    date_str = target_date.strftime("%Y-%m-%d")
    logger.info(f"--- New Job Started for {date_str} at {datetime.now()} ---")

    # 1. Fetch Stories
    logger.info(f"Fetching stories for {date_str}...")
    today_str = datetime.now().strftime("%Y-%m-%d")
    logger.debug(f"date_str={date_str}, today_str={today_str}")
    
    stories = fetch_stories_by_date(date_str, limit=10)
    
    if not stories and date_str == today_str:
        logger.debug("Condition met, calling fetch_top_stories")
        stories = fetch_top_stories(limit=10)
        
    logger.info(f"Fetched {len(stories)} stories.")
    
    processed_articles = []
    
    # 2. Process each story
    for story in stories:
        title = story.get('title', 'No Title')
        url = story.get('url')
        if not url:
            continue
            
        if "youtube.com" in url or "youtu.be" in url:
            logger.info(f"Skipping YouTube URL: {url}")
            continue

        logger.info(f"Processing: {title}")
        
        # Scrape
        text = scrape_article(url)
        if not text:
            logger.warning(f"  - [FAIL] Scraping failed or too short. Skipping: {url}")
            continue
        
        logger.info(f"  - [SUCCESS] Scraped {len(text)} characters.")
        
        # Summarize
        summary = summarize_article(title, text)
        if "エラー" in summary or "error" in summary.lower():
            logger.warning(f"  - Summarization failed for: {title}")
        else:
            logger.info("  - Summary generated.")
        
        processed_articles.append({
            'title': title,
            'summary': summary
        })
        
        # Pacing to avoid API rate limits (e.g., 5 RPM)
        logger.info("  - Waiting 15s to respect API rate limits...")
        time.sleep(15)

    logger.info(f"Final processed articles list length: {len(processed_articles)}")
    if not processed_articles:
        logger.info(f"No articles processed successfully for {date_str}. Skipping final steps.")
        return

    # 4. Generate Audio
    output_file = os.path.join(OUTPUT_DIR, f"podcast_{date_str}.mp3")
    music_file = "app/assets/background_music.mp3"
    
    try:
        logger.info(f"Starting audio generation for {len(processed_articles)} articles...")
        create_podcast_audio(processed_articles, output_file, music_path=music_file)
        logger.info("Audio generation complete!")
        
        # 4.1. Save/Update Metadata (JSON) for RSS enhancement
        metadata_file = os.path.join(OUTPUT_DIR, f"podcast_{date_str}.json")
        try:
            # Get duration and size
            from mutagen.mp3 import MP3
            audio = MP3(output_file)
            duration_seconds = int(audio.info.length)
            size_bytes = os.path.getsize(output_file)
            
            # Create a enhanced metadata structure
            metadata = {
                "date": date_str,
                "duration_seconds": duration_seconds,
                "size_bytes": size_bytes,
                "articles": processed_articles
            }
            
            with open(metadata_file, "w", encoding="utf-8") as jf:
                json.dump(metadata, jf, ensure_ascii=False, indent=2)
            logger.info(f"Enhanced metadata saved to {metadata_file} (duration={duration_seconds}s, size={size_bytes}B)")
        except Exception as json_err:
            logger.warning(f"Failed to save metadata JSON: {json_err}")

        # 4.2. Update RSS Feed
        rss_file = os.path.join(OUTPUT_DIR, "podcast.xml")
        logger.info(f"Updating RSS feed at: {rss_file}")
        try:
            generate_rss(processed_articles, output_file, BASE_URL, rss_file)
            logger.info("RSS feed update complete!")
            
            # 4.3. Also update root podcast.xml and index.html for easier access
            # Use absolute paths to avoid confusion about CWD
            cwd = os.getcwd()
            root_rss = os.path.join(cwd, "podcast.xml")
            root_index = os.path.join(cwd, "index.html")
            
            logger.info(f"Syncing RSS to root: {root_rss}")
            shutil.copy2(rss_file, root_rss)
            
            output_index = os.path.join(OUTPUT_DIR, "index.html")
            if os.path.exists(output_index):
                logger.info(f"Syncing index.html to root: {root_index}")
                shutil.copy2(output_index, root_index)
                logger.info(f"Root index.html and RSS updated successfully.")
            else:
                logger.warning(f"Source index.html not found at {output_index}, only root RSS updated.")
        except Exception as rss_err:
            logger.error(f"CRITICAL: RSS Generation or sync failed: {rss_err}")

        # 5. Push to GitHub (for GitHub Pages hosting)
        enable_push = os.getenv("ENABLE_GIT_PUSH", "false").lower() == "true"
        if enable_push:
            logger.info("Pushing updates to GitHub...")
            if push_to_github():
                # 6. Cleanup local audio files after successful push (kept in Git history)
                cleanup_local_audio(keep_latest_only=False)
        else:
            logger.info("GitHub push is disabled (ENABLE_GIT_PUSH=false).")
            
    except Exception as e:
        logger.error(f"Error in final steps: {e}")

def push_to_github():
    """Commit and push changes to GitHub."""
    import subprocess
    try:
        # Add /app to safe.directory to avoid ownership issues in Docker
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app"], check=False)
        
        # Configure Git identity
        git_user = os.getenv("GIT_USER_NAME", "RPi Podcast Bot")
        git_email = os.getenv("GIT_USER_EMAIL", "bot@example.com")
        gh_pat = os.getenv("GH_PAT")
        
        subprocess.run(["git", "config", "--global", "user.name", git_user], check=True)
        subprocess.run(["git", "config", "--global", "user.email", git_email], check=True)
        
        # Ensure remote URL is HTTPS and includes PAT for container environments
        if gh_pat:
            try:
                remote_url_proc = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
                if remote_url_proc.returncode == 0:
                    remote_url = remote_url_proc.stdout.strip()
                    safe_url = remote_url
                    if "@" in safe_url and "://" in safe_url:
                        safe_url = safe_url.split("://")[0] + "://***:***@" + safe_url.split("@")[1]
                    logger.info(f"Current remote: {safe_url}")
                    # Target URL structure: https://<user>:<token>@github.com/user/repo.git
                    # If it's already an authenticated URL, we may need to replace the old token or just ensure it's correct.
                    
                    # 1. Convert SSH/Git protocol to HTTPS if needed
                    if remote_url.startswith("git@github.com:") or remote_url.startswith("ssh://"):
                        repo_path = remote_url.split(":")[-1].replace(".git", "")
                        remote_url = f"https://github.com/{repo_path}"
                    
                    # 2. Extract the base repository path (e.g., tetsuji16/hacker-news.git)
                    if "github.com/" in remote_url:
                        repo_suffix = remote_url.split("github.com/")[-1]
                        # 3. Construct the new authenticated URL
                        new_url = f"https://{git_user}:{gh_pat}@github.com/{repo_suffix}"
                        
                        if new_url != remote_url:
                            subprocess.run(["git", "remote", "set-url", "origin", new_url], check=True, capture_output=True)
                            logger.info("Updated remote URL with GH_PAT for authenticated push.")
            except Exception as e:
                logger.warning(f"Failed to update remote URL with PAT: {e}")

        # Sync key files to root and add them
        try:
            # Add files to commit: output dir and root meta files
            subprocess.run(["git", "add", "--ignore-removal", "output/", "podcast.xml", "index.html"], check=True)
            
            # Check for changes
            status_proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
            if not status_proc.stdout.strip():
                logger.info("No changes to commit (GitHub is already up to date).")
                return True
                
            # Commit and Push
            commit_msg = f"Update podcast: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            
            # Use explicit push to origin main/master if needed, but simple "git push" should work if upstream is set
            push_proc = subprocess.run(["git", "push"], capture_output=True, text=True)
            if push_proc.returncode != 0:
                logger.error(f"Git push failed (exit code {push_proc.returncode}): {push_proc.stderr}")
                return False
                
            logger.info("SUCCESS: Successfully pushed changes to GitHub!")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed (exit code {e.returncode}): {e.stderr if hasattr(e, 'stderr') else e}")
            return False

    except Exception as e:
        logger.error(f"Critical error in push_to_github: {e}")
        return False

def cleanup_local_audio(keep_latest_only=True):
    """Delete old local MP3 files to save space, assuming they are pushed to GitHub."""
    import glob
    try:
        mp3_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "podcast_*.mp3")))
        if len(mp3_files) <= 1:
            return
            
        # If we want to keep the latest one (today's), remove it from the deletion list
        to_delete = mp3_files[:-1] if keep_latest_only else mp3_files
        
        for f in to_delete:
            try:
                os.remove(f)
                logger.info(f"Deleted local audio file for space optimization: {f}")
            except Exception as e:
                logger.warning(f"Failed to delete {f}: {e}")
                
    except Exception as e:
        logger.error(f"Error during local audio cleanup: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-now", action="store_true", help="Run immediately and exit")
    parser.add_argument("--date", type=str, help="Run for a specific date (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=str, help="Start date for backfill (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date for backfill (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.start_date:
        start = datetime.strptime(args.start_date, "%Y-%m-%d")
        end = datetime.strptime(args.end_date, "%Y-%m-%d") if args.end_date else datetime.now()
        
        current = start
        while current <= end:
            print(f"\n=== BACKFILL: Processing {current.strftime('%Y-%m-%d')} ===")
            job(current)
            current += timedelta(days=1)
            # Small wait between days
            time.sleep(2)
    elif args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")
        job(target)
    elif args.run_now:
        job()
    else:
        schedule_time = os.getenv("SCHEDULE_TIME", "06:00")

        logger.info(f"Scheduler started. Job runs daily at {schedule_time}")
        schedule.every().day.at(schedule_time).do(job)
        
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    main()
