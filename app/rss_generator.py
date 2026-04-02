import json
import os
import glob
from podgen import Podcast, Episode, Media, Person, Category
from mutagen.mp3 import MP3
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger("hn_podcast")

def generate_rss(articles: list, mp3_path: str, base_url: str, output_xml: str):
    p = Podcast(
        name="Hacker News デイリー (日本)",
        description="Hacker Newsの最新トップストーリーを日本語で要約してお届けするポッドキャストです。最新のAI、プログラミング、スタートアップ情報を毎日配信。",
        website="https://news.ycombinator.com",
        explicit=False,
        language="ja-JP",
        image=f"{base_url}HackerNewsLogo.png"
    )
    p.category = Category("Technology", "Software How-To")
    p.author = Person("Tetsuji", "tetsuji.kato@gmail.com")
    p.owner = Person("Tetsuji", "tetsuji.kato@gmail.com")
    
    # These help with search results
    p.subtitle = "Hacker Newsの注目ニュースを日本語で毎日お届け"
    p.keywords = ["Hacker News", "AI", "テクノロジー", "エンジニア", "スタートアップ", "日本語要約", "ニュース"]

    if not base_url.endswith('/'):
        base_url += '/'

    # Iterate over all podcast_*.json files to reconstruct RSS
    # This ensures we find all episodes even if the MP3 was deleted for space optimization
    mp3_dir = os.path.dirname(mp3_path)
    if not mp3_dir:
        mp3_dir = "."
        
    metadata_files = sorted(glob.glob(os.path.join(mp3_dir, "podcast_*.json")))
    logger.info(f"Found {len(metadata_files)} metadata files to process.")

    for metadata_file in metadata_files:
        # Extract date from filename
        date_str = os.path.basename(metadata_file).replace("podcast_", "").replace(".json", "")
        
        # Determine expected MP3 filename
        mp3_filename = f"podcast_{date_str}.mp3"
        mp3_file = os.path.join(mp3_dir, mp3_filename)
        public_url = f"{base_url}{mp3_filename}"
        
        try:
            pub_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.utc)
        except Exception:
            pub_date = datetime.now(pytz.utc)

        # 1. Load data from JSON
        episode_data = {}
        episode_articles = []
        try:
            with open(metadata_file, "r", encoding="utf-8") as jf:
                episode_data = json.load(jf)
                # Handle both formats (legacy list or enhanced dict)
                if isinstance(episode_data, list):
                    episode_articles = episode_data
                else:
                    episode_articles = episode_data.get('articles', [])
        except Exception as e:
            logger.warning(f"Failed to load metadata {metadata_file}: {e}")
            if os.path.abspath(mp3_file) == os.path.abspath(mp3_path):
                episode_articles = articles
        
        # 2. Get duration and size
        duration_seconds = 0
        size_bytes = 0
        
        # Prefer actual file if it exists
        if os.path.exists(mp3_file):
            try:
                audio = MP3(mp3_file)
                duration_seconds = int(audio.info.length)
                size_bytes = os.path.getsize(mp3_file)
            except Exception:
                pass
        
        # Fallback to metadata in JSON if file is missing or scan failed
        if duration_seconds == 0 and isinstance(episode_data, dict):
            duration_seconds = episode_data.get('duration_seconds', 0)
        if size_bytes == 0 and isinstance(episode_data, dict):
            size_bytes = episode_data.get('size_bytes', 0)
            
        # 3. Generate summary content
        if episode_articles:
            sections = []
            for a in episode_articles:
                title = a.get('title', 'No Title')
                body = a.get('summary', '').strip()
                
                # If using the new format with [Summary] section
                if "[Summary]" in body:
                    # Extract content after [Summary]
                    summary_part = body.split("[Summary]")[-1].strip()
                    # Clean up any trailing scripts or labels
                    summary_lines = [line.strip("- ").strip() for line in summary_part.split("\n") if line.strip().startswith("-")]
                    if summary_lines:
                        bullet_list = "\n".join([f"・{line}" for line in summary_lines])
                        sections.append(f"■ {title}\n{bullet_list}")
                    else:
                        sections.append(f"■ {title}\n{summary_part}")
                # Legacy split by line but keep it cleaner
                clean_body = body.replace("[Summary]", "").strip()
                # Remove script lines
                clean_lines = [line for line in clean_body.split("\n") if "Nana:" not in line and "Keita:" not in line and not line.strip().startswith("[")]
                clean_body = "\n".join(clean_lines).strip()
                
                if clean_body:
                    sections.append(f"## ■ {title}\n{clean_body}")
                else:
                    sections.append(f"## ■ {title}")
            
            header = "各記事の要約を「である」調でまとめる。\n\n---\n\n"
            summary = header + "\n\n".join(sections) + "\n\n---\n日本語の要約をお楽しみください。"
        else:
            summary = f"{date_str}版のHacker Newsニュース要約です。日本語読み上げでお届けします。"

        e = p.add_episode(Episode(
            title=f"Hacker News アップデート {date_str}",
            summary=summary,
            publication_date=pub_date
        ))
        
        e.media = Media(public_url, size_bytes, type="audio/mpeg", duration=timedelta(seconds=duration_seconds))
    
    p.rss_file(output_xml)
    logger.info(f"RSS feed generated with {len(metadata_files)} episodes at {output_xml}")
    
    # Also generate a simple index.html for SEO
    index_html = os.path.join(os.path.dirname(output_xml), "index.html")
    generate_index_html(p, index_html)

def generate_index_html(podcast, output_path):
    """Generate a clean, SEO-friendly HTML landing page for the podcast."""
    episodes_html = ""
    for e in reversed(podcast.episodes): # Latest first
        safe_summary = e.summary.replace("\n", "<br>")
        episodes_html += f"""
        <article class="episode">
            <h2>{e.title}</h2>
            <p class="date">{e.publication_date.strftime('%Y-%m-%d')}</p>
            <div class="summary">{safe_summary}</div>
            <audio controls src="{e.media.url}"></audio>
            <hr>
        </article>
        """
        
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{podcast.name}</title>
        <meta name="description" content="{podcast.description}">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
            h1 {{ color: #000; border-bottom: 2px solid #ff6600; padding-bottom: 10px; }}
            .episode {{ margin-bottom: 40px; padding: 20px; background: #f9f9f9; border-radius: 8px; }}
            .date {{ color: #666; font-size: 0.9em; }}
            .summary {{ margin: 15px 0; font-size: 0.95em; }}
            audio {{ width: 100%; margin-top: 10px; }}
            .rss-link {{ display: inline-block; background: #ff6600; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h1>{podcast.name}</h1>
        <p>{podcast.description}</p>
        <a href="podcast.xml" class="rss-link">RSSフィードを購読 (Apple/Spotify等)</a>
        <section class="episodes">
            {episodes_html}
        </section>
        <footer>
            <p>&copy; {datetime.now().year} {podcast.author.name if podcast.author else ""}</p>
        </footer>
    </body>
    </html>
    """
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Index HTML generated at {output_path}")
