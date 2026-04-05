from app.application.generate_daily_summary import execute_daily_summary

def run():
    print("\n=== DAILY HEALTH SUMMARY ===\n")

    data = execute_daily_summary()

    print(data["summary_text"])

    print("\n=== AI INSIGHTS ===\n")
    print(data["ai_insights"])


if __name__ == "__main__":
    run()