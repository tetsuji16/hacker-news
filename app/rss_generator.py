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
        website="https://tetsuji16.github.io/hacker-news/",
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
                else:
                    # Legacy split by line but keep it cleaner
                    clean_body = body.replace("[Summary]", "").strip()
                    # Remove script lines
                    clean_lines = []
                    for line in clean_body.split("\n"):
                        if line.strip().startswith("["):
                            continue
                        # Remove the prefix instead of the entire line
                        line = line.replace("Nana: ", "").replace("Keita: ", "").replace("Nana:", "").replace("Keita:", "")
                        clean_lines.append(line.strip())
                    clean_body = "\n".join(clean_lines).strip()
                    
                    if clean_body:
                        sections.append(f"## ■ {title}\n{clean_body}")
                    else:
                        sections.append(f"## ■ {title}")
            
            summary = "\n\n".join(sections)
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
        # Also clean up the '## ■ ' string into actual bold or clean headers
        safe_summary = safe_summary.replace("## ■ ", "<strong>■ ").replace("<br><br><strong>", "</strong><br><br><strong>")
        # Add the final closing strong tag if we started one
        if "<strong>" in safe_summary and safe_summary.count("<strong>") > safe_summary.count("</strong>"):
            safe_summary += "</strong>"

        episodes_html += f"""
        <article class="episode">
            <h2>{e.title}</h2>
            <div class="date-badge">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                {e.publication_date.strftime('%Y-%m-%d')}
            </div>
            <div class="summary">{safe_summary}</div>
            <div class="player-wrapper">
                <audio controls src="{e.media.url}"></audio>
            </div>
        </article>
        """
        
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{podcast.name} - AI Podcast</title>
        <meta name="description" content="{podcast.description}">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-color: #0f172a;
                --text-main: #f8fafc;
                --text-muted: #94a3b8;
                --accent: #38bdf8;
                --accent-hover: #0284c7;
                --card-bg: rgba(30, 41, 59, 0.7);
                --card-border: rgba(51, 65, 85, 0.5);
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Inter', 'Noto Sans JP', sans-serif;
                line-height: 1.7;
                background-color: var(--bg-color);
                color: var(--text-main);
                background-image: radial-gradient(circle at top right, #1e293b, transparent 400px),
                                  radial-gradient(circle at bottom left, #172554, transparent 400px);
                background-attachment: fixed;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                padding: 40px 20px;
            }}
            header {{
                text-align: center;
                margin-bottom: 50px;
                animation: fadeInDown 0.8s ease-out;
            }}
            h1 {{
                font-size: 2.5rem;
                font-weight: 700;
                background: linear-gradient(135deg, #38bdf8, #818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 15px;
                letter-spacing: -0.02em;
            }}
            .description {{
                color: var(--text-muted);
                font-size: 1.1rem;
                max-width: 600px;
                margin: 0 auto 25px;
            }}
            .rss-link {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: var(--accent);
                color: #fff;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 30px;
                font-weight: 600;
                font-size: 0.95rem;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(56, 189, 248, 0.3);
            }}
            .rss-link:hover {{
                background: var(--accent-hover);
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(56, 189, 248, 0.5);
            }}
            .episodes {{
                display: flex;
                flex-direction: column;
                gap: 30px;
            }}
            .episode {{
                background: var(--card-bg);
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 30px;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                animation: fadeInUp 0.6s ease-out backwards;
            }}
            .episode:hover {{
                transform: translateY(-4px);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                border-color: rgba(56, 189, 248, 0.3);
            }}
            .episode h2 {{
                font-size: 1.5rem;
                font-weight: 600;
                margin-bottom: 12px;
                color: #e2e8f0;
            }}
            .date-badge {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                background: rgba(15, 23, 42, 0.6);
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                color: var(--accent);
                font-weight: 500;
                margin-bottom: 20px;
            }}
            .summary {{
                color: #cbd5e1;
                font-size: 0.95rem;
                margin-bottom: 25px;
            }}
            .summary strong {{
                color: var(--accent);
                font-weight: 600;
                display: block;
                margin-top: 15px;
                margin-bottom: 5px;
            }}
            .player-wrapper {{
                background: rgba(15, 23, 42, 0.4);
                padding: 15px;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }}
            audio {{
                width: 100%;
                height: 40px;
                outline: none;
            }}
            audio::-webkit-media-controls-panel {{
                background-color: #f8fafc;
            }}
            footer {{
                margin-top: 60px;
                text-align: center;
                color: var(--text-muted);
                font-size: 0.9rem;
                padding-top: 20px;
                border-top: 1px solid var(--card-border);
            }}
            @keyframes fadeInDown {{
                from {{ opacity: 0; transform: translateY(-20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            @keyframes fadeInUp {{
                from {{ opacity: 0; transform: translateY(20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            @media (max-width: 600px) {{
                h1 {{ font-size: 2rem; }}
                .episode {{ padding: 20px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>{podcast.name}</h1>
                <p class="description">{podcast.description}</p>
                <a href="podcast.xml" class="rss-link">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11a9 9 0 0 1 9 9"></path><path d="M4 4a16 16 0 0 1 16 16"></path><circle cx="5" cy="19" r="1"></circle></svg>
                    RSSフィードを購読 (Apple/Spotify等)
                </a>
            </header>
            
            <section class="episodes">
                {episodes_html}
            </section>
            
            <footer>
                <p>&copy; {datetime.now().year} {podcast.author.name if podcast.author else "AI Generated"}</p>
            </footer>
        </div>
    </body>
    </html>
    """
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Index HTML generated at {output_path}")
