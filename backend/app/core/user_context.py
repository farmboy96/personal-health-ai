"""
Static user context injected into AI health prompts.
This lets the interpreter produce targeted analysis instead of hedging
across possibilities it could infer from the data anyway.

Edit freely as circumstances change. Avoid putting anything here you
would not want sent to the OpenAI API.
"""

USER_CONTEXT = """
Subject profile:
- Sex: male
- Age: [FILL IN]
- Height/weight: [FILL IN or leave blank]
- Current medications/therapies: [FILL IN — e.g. "none", "TRT 100mg/wk cypionate", "statin X mg", etc.]
- Current supplements: [FILL IN or leave blank]
- Relevant conditions/history: [FILL IN or leave blank]
- Lifestyle notes: [FILL IN — e.g. "lifts 3x/wk, sedentary desk job", "frequent travel", etc.]
""".strip()
