import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"


def analyze_emails(emails):
    print(f"email:{emails}")
    prompt = f"""
You are an assignment detection agent.

Analyze all of the following unread emails.

Return ONLY assignments that require the student to take action.
Ignore newsletters, notifications, advertisements, conversations,
receipts, announcements that require no action, etc.

EMAILS:

{json.dumps(emails, indent=2)}

Return exactly this JSON structure:

{{
    "assignments": [
        {{
            "email_id": "string",
            "assignment_title": "string",
            "deadline": "string or null",
            "question_in_pdf": true,
            "question": "string or null",
            "relevant_attachments": ["string"],
            "action": "solve_and_submit"
        }}
    ]
}}

Rules:

- If the assignment question is contained in the email itself:
  question_in_pdf = false and put the question in question.
- If the question is contained in a PDF attachment:
  question_in_pdf = true and question = null.
- relevant_attachments must contain only attachments relevant to the assignment.
- Ignore unrelated emails.
- Do not invent information.
- Return valid JSON only.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You classify emails and return strict JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"},
        reasoning_effort="medium"
    )

    return json.loads(response.choices[0].message.content)
