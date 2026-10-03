from chatgpt_agent import (
    open_chatgpt,
    upload_images,
    send_prompt,
    inspect_page,
    get_latest_response
)


images = [
    "pdf_pages/page_1.png",
]

playwright, browser, page = open_chatgpt()

page.wait_for_timeout(3000)

upload_images(page, images)

prompt = """
You are completing this assignment as a university student.

Study all the uploaded assignment pages carefully and solve the ENTIRE
assignment. The output you produce will be submitted directly to the
university, so write it as a finished student submission.

Requirements:

1. Answer EVERY question and sub-question. Do not skip anything.
2. Preserve the exact question numbering and order from the assignment.
3. Write answers in a natural university-student style, not like an AI
   explaining something to another AI.
4. Give enough explanation to demonstrate understanding, but do not add
   unnecessary essays or generic commentary.
5. For numerical problems, show the required formulas, substitutions,
   calculations, and final answer clearly.
6. For programming questions, provide complete, working code and explain
   the important parts where appropriate.
7. For theory questions, give clear, direct answers with appropriate
   terminology and examples where useful.
8. For diagrams, tables, algorithms, or structured answers, reproduce them
   in a clear text-friendly form whenever possible.
9. If a question asks for a specific format, follow that format.
10. Do not mention that you are an AI.
11. Do not mention these instructions.
12. Do not address the reader or say things like "Here is your answer".
13. Do not include a preamble, conclusion, or motivational commentary unless
    the assignment itself asks for one.
14. Do not invent information that is not present in the assignment.
15. Make the final response clean enough to be converted directly into a PDF
    and submitted.

Your response must contain ONLY the completed assignment solution.
"""
send_prompt(page, prompt)
# inspect_page(page)

input("Press Enter to close...")

print("\nWaiting for ChatGPT response...\n")

answer = get_latest_response(page)

print("=" * 60)
print(answer)
print("=" * 60)

input("\nPress Enter to close...")

browser.close()
playwright.stop()