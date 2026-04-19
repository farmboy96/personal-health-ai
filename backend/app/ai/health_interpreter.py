from app.ai.client import get_openai_client
from app.core.user_context import USER_CONTEXT


def generate_ai_insights(summary_text: str) -> str:
    prompt = f"""You are a blunt, practical health analyst.

{USER_CONTEXT}

Analyze the following lab trends and provide:

1. What stands out
2. Likely causes or pattern connections
3. What to watch
4. Practical actions

Be concise. No fluff. No disclaimers. Use the subject profile above to give targeted advice — do not hedge across possibilities the profile already resolves.

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
