import asyncio
import edge_tts
from pydub import AudioSegment
import os
import re
import logging

logger = logging.getLogger("hn_podcast")

NANA_VOICE = "ja-JP-NanamiNeural"
KEITA_VOICE = "ja-JP-KeitaNeural"
EN_VOICE = "en-US-AriaNeural"


async def _generate_audio_segment(text: str, output_path: str) -> None:
    """Generate audio for a text segment, switching voices based on character labels and language."""
    
    # Parse character labels (Nana: or Keita:)
    lines = text.split('\n')
    all_segments = []
    
    last_speaker = "Keita" # Assume start with Nana unless specified
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Stop processing if we hit the summary section
        if "[Summary]" in line or "要約" in line:
            break

            
        # Clean up markdown bolding and any stray SSML tags
        line = line.replace("**", "").replace("_", "")
        line = re.sub(r'<[^>]*>', '', line)
        
        # Skip section headers or separators
        if line.startswith("[") or line.startswith("#") or "---" in line or "***" in line:
            continue


        # Handle different name formats or lack thereof
        current_jp_voice = NANA_VOICE
        
        # Check for explicit labels
        if line.startswith("Nana:") or line.startswith("**Nana:**") or line.startswith("Nana :"):
            line = re.sub(r'^\**Nana:\**\s*', '', line).strip()
            current_jp_voice = NANA_VOICE
            last_speaker = "Nana"
        elif line.startswith("Keita:") or line.startswith("**Keita:**") or line.startswith("Keita :"):
            line = re.sub(r'^\**Keita:\**\s*', '', line).strip()
            current_jp_voice = KEITA_VOICE
            last_speaker = "Keita"
        elif line.startswith(":"):
            # Handle the case where AI forgets the name but keeps the colon
            line = line.lstrip(":").strip()
            # Alternate speaker
            if last_speaker == "Nana":
                current_jp_voice = KEITA_VOICE
                last_speaker = "Keita"
            else:
                current_jp_voice = NANA_VOICE
                last_speaker = "Nana"
        else:
            # If no name, alternate speaker to maintain conversation flow
            if len(line) < 2:
                continue
                
            if last_speaker == "Nana":
                current_jp_voice = KEITA_VOICE
                last_speaker = "Keita"
            else:
                current_jp_voice = NANA_VOICE
                last_speaker = "Nana"


            
        if not line:
            continue
            
        # Split line into JP and EN fragments for voice switching
        # Very basic regex to find English-ish words (alphanumeric and some punctuation)
        # Improvement: edge-tts actually supports SSML <voice> tags in one go, 
        # but parsing fragments manually gives more control.
        # However, for simplicity and robustness with SSML, we'll use a hybrid approach.
        
        # If the line contains SSML tags, we need to wrap it correctly.
        # edge-tts Communicate(text) can take raw text or SSML.
        # To switch voices within a line, we MUST use SSML.
        
        # Pattern to find English words to wrap in EN voice
        # We look for sequences of 2 or more English words or technical terms.
        en_pattern = r'([a-zA-Z0-9\-\.\s]{4,})' 
        
        # If we want to be super detailed, we'd wrap these in <voice name="..."> tags.
        # For now, let's keep it simpler: if the line is majority English, use EN voice.
        # Actually, let's just use the assigned voice for the whole line but wrap it in SSML 
        # to preserve the <break> tags from the summarizer.
        
        all_segments.append({'text': line, 'voice': current_jp_voice})

    if not all_segments:
        return

    combined = AudioSegment.empty()
    temp_files = []
    
    log_path = "output/audio_gen.log" # Relative to project root
    try:
        for i, seg in enumerate(all_segments):
            temp_part = f"{output_path}_part_{i}.mp3"
            
            communicate = edge_tts.Communicate(seg['text'], seg['voice'])
            
            # Add retry logic for Edge TTS network instability (especially 503 errors)
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    # If file accidentally left behind from a failed attempt, clear it
                    if os.path.exists(temp_part):
                        os.remove(temp_part)
                        
                    await communicate.save(temp_part)
                    
                    # Verify file was actually created and has content
                    if os.path.exists(temp_part) and os.path.getsize(temp_part) > 100:
                        break
                    else:
                        raise Exception("Generated audio file is empty or missing")
                        
                except Exception as eval_err:
                    curr_wait = min(60, 2 * (attempt + 1)) # Linear/Exp growth backoff
                    if attempt < max_retries - 1:
                        logger.warning(f"Edge TTS error (attempt {attempt+1}/{max_retries}): {eval_err}. Retrying in {curr_wait}s...")
                        await asyncio.sleep(curr_wait)
                    else:
                        logger.error(f"FATAL Edge TTS error after {max_retries} attempts: {eval_err}")
                        raise  # Re-raise to abort this article's generation
            
            temp_files.append(temp_part)
            combined += AudioSegment.from_mp3(temp_part)
            
        combined.export(output_path, format="mp3")
    except Exception as e:
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    logger.warning(f"Could not remove temp file {f}: {e}")

def generate_tts(text: str, output_path: str):
    """Wrapper to run async TTS generation synchronously."""
    asyncio.run(_generate_audio_segment(text, output_path))

def create_podcast_audio(articles: list, output_file: str, music_path: str = None):
    """
    Combine intros, article summaries, and outro into a single MP3.
    articles: list of dicts with 'title' and 'summary'
    """
    
    combined = AudioSegment.empty()
    temp_dir = "temp_audio"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Intro (Anonymous)
    intro_text = "Nana: こんにちは。Hacker Newsの最新アップデートをお届けします。\nKeita: 今日もテック界の注目ニュースが目白押しですね。早速見ていきましょう。"
    intro_path = os.path.join(temp_dir, "intro.mp3")
    generate_tts(intro_text, intro_path)
    combined += AudioSegment.from_mp3(intro_path)
    combined += AudioSegment.silent(duration=1000)

    # Articles
    for i, article in enumerate(articles, 1):
        # Topic Transition
        title = article['title']
        # Clean title for transition
        topic = title.split(':')[0] if ':' in title else title
        prefix = "まず" if i == 1 else "次は"
        transition_text = f"Nana: {prefix}、{topic}に関する話題です。<break time=\"500ms\"/>"
        transition_path = os.path.join(temp_dir, f"trans_{i}.mp3")
        generate_tts(transition_text, transition_path)
        combined += AudioSegment.from_mp3(transition_path)
        combined += AudioSegment.silent(duration=500)

        # Summary
        summary_text = article['summary']
        summary_path = os.path.join(temp_dir, f"summary_{i}.mp3")
        try:
            generate_tts(summary_text, summary_path)
            if os.path.exists(summary_path):
                combined += AudioSegment.from_mp3(summary_path)
                combined += AudioSegment.silent(duration=1500)
        except Exception as e:
            logger.warning(f"Failed to generate audio for article {i}: {article['title']}: {e}")


    # Outro (Anonymous)
    outro_text = "Nana: 本日のニュースは以上です。お聞きいただきありがとうございました。\nKeita: また次回お会いしましょう。"
    outro_path = os.path.join(temp_dir, "outro.mp3")
    generate_tts(outro_text, outro_path)
    combined += AudioSegment.from_mp3(outro_path)
    
    # Add background music if provided
    if music_path and os.path.exists(music_path):
        try:
            bg_music = AudioSegment.from_file(music_path)
            # Loop music to match podcast length
            bg_music = bg_music * (len(combined) // len(bg_music) + 1)
            bg_music = bg_music[:len(combined)]
            # Reduce volume of music (-20dB to -30dB is usually good for background)
            bg_music = bg_music - 25 
            # Fade in/out
            bg_music = bg_music.fade_in(2000).fade_out(3000)
            combined = combined.overlay(bg_music)
        except Exception as e:
            logger.warning(f"Could not add background music: {e}")

    # Export final file and cleanup
    try:
        if len(combined) < 10000: # Less than 10 seconds is probably a failure
            logger.error(f"CRITICAL: Final podcast audio {output_file} is too short ({len(combined)/1000:.1f}s). Not exporting.")
            if os.path.exists(output_file):
                 os.remove(output_file)
            return False
            
        combined.export(output_file, format="mp3")
        logger.info(f"Successfully generated podcast audio at {output_file} ({len(combined)/1000:.1f}s)")
        return True
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            for f in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, f))
                except Exception:
                    pass
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass

