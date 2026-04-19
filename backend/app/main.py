from app.application.generate_daily_summary import execute_daily_summary

import sys

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run():
    print("\n=== DAILY HEALTH SUMMARY ===\n")

    data = execute_daily_summary()

    print(data["summary_text"])

    print("\n=== AI INSIGHTS ===\n")
    print(data["ai_insights"])


if __name__ == "__main__":
    run()