import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

model = genai.GenerativeModel('models/gemini-flash-latest')

import logging
import time
import requests
import json

logger = logging.getLogger("hn_podcast")


# List of Google AI Studio models to try in sequence
GOOGLE_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-8b",
]

def summarize_with_openrouter(prompt: str) -> str:
    """Fallback summarization using OpenRouter."""
    logger.info("  - Attempting fallback summarization with OpenRouter (Google: Gemini 2.0 Flash)...")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("    OpenRouter API key not found.")
        return None
        
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            data=json.dumps({
                "model": "google/gemini-2.0-flash-001",
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
        )
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            logger.error(f"    OpenRouter error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"    OpenRouter exception: {e}")
        return None

def summarize_article(title: str, text: str) -> str:
    """
    Summarize the article text using a chain of Google AI Studio models.
    Falls back to OpenRouter if all Google models fail.
    """
    if not text:
        return "Nana: 申し訳ありませんが、この記事の内容にアクセスできませんでした。\nKeita: そうですか。たまにサイト側の制限で読み取れないこともありますよね。"

    prompt = f"""
    あなたはテック系ポッドキャストの台本作家です。
    以下のHacker Newsの記事をもとに、2人のホスト（NanaとKeita）による自然な会話形式のポッドキャスト用台本と、その内容の要約を作成してください。

    キャラクター設定:
    - Nana: 知識豊富で落ち着いた雰囲気。
    - Keita: 好奇心旺盛で、リスナーの視点から質問を投げかける聞き手。

    出力構成:
    1. [Podcast Script] セクション: 2人の会話台本。
    2. [Summary] セクション: 記事の要点を「である」調（常体）でまとめた、1段落程度の詳細な説明（日本語）。箇条書きは使用せず、文脈のある説明にしてください。

    制約事項 (重要):
    - [Podcast Script] 内の形式は必ず「Nana: [セリフ]」「Keita: [セリフ]」で始めてください。
    - **セリフの中に「Nana」や「Keita」といった名前、または自分たちの名前を名乗る表現は一切含めないでください。**
    - [Summary] は必ず「である」調で記載し、1つ1つの記事について背景や技術的な詳細を含めて詳細に説明してください。
    - 技術用語、製品名、固有名称などの英単語は、可能な限り英語のまま記載してください。
    - 全体を通して自然な日本語を使用してください。

    Title: {title}
    Content:
    {text[:15000]}

    Output:
    """
    
    log_file = "output/summarizer.log"
    
    # List of phrases that indicate the model failed to find details
    NOT_FOUND_INDICATORS = [
        "この記事の詳細は現在取得できませんでした",
        "この記事の内容にアクセスできませんでした",
        "詳細を把握することができませんでした",
        "情報が不足しており",
        "取得できませんでした"
    ]
    
    for model_name in GOOGLE_MODELS:
        logger.info(f"  - Attempting summarization with {model_name}...")
        
        max_model_retries = 2
        for model_attempt in range(max_model_retries):
            try:
                current_model = genai.GenerativeModel(f"models/{model_name}")
                response = current_model.generate_content(prompt)
                # Check if response actually has text
                if response and response.text:
                    summary_text = response.text.strip()
                    
                    is_missing_details = any(indicator in summary_text for indicator in NOT_FOUND_INDICATORS)
                    if is_missing_details:
                        logger.warning(f"    {model_name} returned 'missing details' response. Trying next model...")
                        break 
                        
                    logger.info(f"    {model_name} success!")
                    return summary_text
                else:
                    logger.warning(f"    {model_name} returned empty or filtered response.")
                    break 
                    
            except Exception as e:
                if "429" in str(e):
                    if model_attempt < max_model_retries - 1:
                        logger.warning(f"    {model_name} Rate Limit (429). Waiting 60s for retry {model_attempt+1}...")
                        time.sleep(60)
                        continue 
                    else:
                        logger.warning(f"    {model_name} Rate Limit (429) persists. Trying next model...")
                        break 
                else:
                    logger.error(f"    {model_name} error: {e}")
                    break 

    # If all Google models are exhausted, try OpenRouter
    logger.info("  - Exhausted all specified Google AI Studio models. Trying OpenRouter...")
    or_summary = summarize_with_openrouter(prompt)
    if or_summary:
        logger.info("    OpenRouter success!")
        return or_summary

    # Final fallback if everything fails
    return "Nana: 申し訳ありませんが、この記事の詳細は現在取得できませんでした。\nKeita: そうなんですね。残念ですが、次の話題に行きましょう。"
