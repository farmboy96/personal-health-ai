from app.ai.client import get_openai_client

def generate_ai_insights(summary_text: str) -> str:
    prompt = f"""
You are a blunt, practical health analyst.

Analyze the following lab trends and provide:

1. What stands out
2. Likely causes or pattern connections
3. What to watch
4. Practical actions

Be concise. No fluff. No disclaimers.

Data:
{summary_text}
"""
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You analyze health data and give concise, practical insights."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    return response.choices[0].message.content.strip()
