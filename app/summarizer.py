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
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
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
    以下のHacker Newsの記事をもとに、2人のホスト（NanaとKeita）による、耳で聞いて自然で面白いポッドキャスト用台本と、その内容の要約を作成してください。

    キャラクター設定:
    - Nana: ポッドキャストのメインホスト。IT業界の動向に詳しく、落ち着いた頼れる雰囲気。
    - Keita: サブホスト。最新ガジェットや開発者ツールに好奇心旺盛で、リスナーの代表としてNanaに鋭い質問や疑問を投げかける。

    出力構成:
    1. [Podcast Script] セクション: 2人の会話台本。
    2. [Summary] セクション: 記事の要点を「である」調（常体）でまとめた、1段落程度の詳細な説明（日本語）。箇条書きは使用せず、文脈のある説明にしてください。

    制約事項 (重要):
    - **台本の全てのセリフは必ず「Nana: [セリフ]」または「Keita: [セリフ]」の形式で始めてください。名前を省略したり、":" だけで始めたりすることは絶対にしないでください。**
    - 口調はポッドキャストとして自然な「です・ます」または適度な崩した表現（〜だよ、〜だね、〜かな？）を使用し、話し言葉としてリズムが良いものにしてください。
    - 「なるほど」「へぇー！」「確かに」といった相槌や驚きの表現を適宜混ぜて、2人の掛け合いを生き生きとさせてください。
    - Keitaは単に同意するだけでなく、「それって○○ということ？」や「具体的にどう役に立つの？」といった深掘りする質問を一言添えてください。
    - セリフの中に「Nana」や「Keita」という自分たちの名前を名乗る不自然な表現は含めないでください。
    - [Summary] は必ず「である」調で記載し、技術的な背景や詳細を含めてください。
    - 技術用語、製品名などの固有名詞は、英語のまま記載してください。

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
