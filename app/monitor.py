import os
import time
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

LOG_FILE = "output/pipeline.log"
RSS_FILE = "output/podcast.xml"
OUTPUT_DIR = "output"

def audit():
    report = {
        "timestamp": datetime.now().isoformat(),
        "errors": [],
        "missing_files": [],
        "rss_status": "Checking...",
        "completeness": {}
    }

    # 1. Check Log for Critical Failures
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-1000:]: # Check last 1000 lines
                if "CRITICAL" in line or "Traceback" in line:
                    report["errors"].append(line.strip())
    
    # 2. Check RSS Feed for Bulleted summaries
    if os.path.exists(RSS_FILE):
        try:
            tree = ET.parse(RSS_FILE)
            root = tree.getroot()
            channel = root.find("channel")
            items = channel.findall("item")
            report["rss_item_count"] = len(items)
            
            missing_summary_count = 0
            for item in items:
                desc = item.find("description").text if item.find("description") is not None else ""
                if not desc or "[Summary]" not in desc:
                    missing_summary_count += 1
            
            report["rss_status"] = f"OK ({len(items)} items, {missing_summary_count} missing bulleted summaries)"
        except Exception as e:
            report["rss_status"] = f"Error parsing RSS: {e}"

    # 3. Check for specific date range completeness
    expected_dates = []
    # Mar 1-14
    start = datetime(2026, 3, 1)
    for i in range(14):
        expected_dates.append((start + timedelta(days=i)).strftime("%Y-%m-%d"))
    # Mar 17-22
    start = datetime(2026, 3, 17)
    for i in range(6):
        expected_dates.append((start + timedelta(days=i)).strftime("%Y-%m-%d"))
    # Mar 23-24
    expected_dates.extend(["2026-03-23", "2026-03-24"])

    for ds in expected_dates:
        json_path = os.path.join(OUTPUT_DIR, f"podcast_{ds}.json")
        mp3_path = os.path.join(OUTPUT_DIR, f"podcast_{ds}.mp3")
        
        status = {
            "json": os.path.exists(json_path),
            "mp3": os.path.exists(mp3_path)
        }
        report["completeness"][ds] = status
        
        if not status["json"] or not status["mp3"]:
            report["missing_files"].append(ds)

    # Write report
    report_file = os.path.join(OUTPUT_DIR, "audit_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Audit complete. Report written to {report_file}")

if __name__ == "__main__":
    print(f"Monitor started at {datetime.now()}. Waiting 3 hours...")
    time.sleep(10800) # 3 hours
    print(f"Waking up at {datetime.now()}. Running audit...")
    audit()
