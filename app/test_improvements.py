import os
import sys
from datetime import datetime

# Add the project root to sys.path to import local modules
sys.path.append(os.getcwd())

from app.audio_generator import create_podcast_audio
from app.rss_generator import generate_rss
from app.summarizer import summarize_article

def test_improvements():
    print("=== Testing Audio Improvements ===")
    
    # 1. Mock articles
    test_articles = [
        {
            "title": "Breaking News: New Gemini 1.5 Pro features",
            "summary": "Nana: 文末にSSMLタグが含まれているかテストします。<break time=\"1s\"/> Gemini 1.5 Pro is amazing! \nKeita: 確かにそうですね。Scalabilityが向上しています。"
        },
        {
            "title": "Rust vs Go in 2026",
            "summary": "Nana: Rust and Go are compared here. <break time=\"500ms\"/>\nKeita: どちらもモダンな言語ですね。"
        }
    ]
    
    # 2. Test Audio Generation
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    output_audio = os.path.join(output_dir, "test_podcast.mp3")
    
    print(f"Generating test audio at {output_audio}...")
    # Using a dummy or non-existent music path to test fallback
    create_podcast_audio(test_articles, output_audio, music_path="non_existent.mp3")
    
    if os.path.exists(output_audio):
        print(f"SUCCESS: Test audio generated ({os.path.getsize(output_audio)} bytes).")
    else:
        print("FAIL: Test audio not generated.")
        return

    # 3. Test RSS Generation
    output_rss = os.path.join(output_dir, "test_podcast.xml")
    base_url = "https://example.github.io/newscast/"
    
    print(f"Generating test RSS at {output_rss}...")
    generate_rss(test_articles, output_audio, base_url, output_rss)
    
    if os.path.exists(output_rss):
        print(f"SUCCESS: Test RSS generated.")
        with open(output_rss, "r", encoding="utf-8") as f:
            content = f.read()
            if "Technology" in content and "Hacker News" in content:
                print("SUCCESS: RSS metadata looks correct.")
            else:
                print("FAIL: RSS metadata missing expected tags.")
    else:
        print("FAIL: Test RSS not generated.")

if __name__ == "__main__":
    test_improvements()
