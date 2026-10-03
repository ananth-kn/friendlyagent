from gmail import (
    get_gmail_service,
    get_unread_emails,
    download_assignment_attachments
)

from llm import analyze_emails
from pdf_to_images import pdf_to_images
from chatgpt_agent import (
    open_chatgpt,
    upload_images,
    send_prompt,
    get_latest_response
)


def main():

    # -----------------------------
    # 1. Gmail
    # -----------------------------

    service = get_gmail_service()

    emails = get_unread_emails(
        service,
        max_results=2
    )

    print(f"Found {len(emails)} unread emails.")

    if not emails:
        return

    # -----------------------------
    # 2. Analyze emails
    # -----------------------------

    result = analyze_emails(emails)

    assignments = result.get(
        "assignments",
        []
    )

    print(
        f"Found {len(assignments)} assignments."
    )

    # -----------------------------
    # 3. Open ChatGPT once
    # -----------------------------

    playwright, browser, page = open_chatgpt()

    try:

        for assignment in assignments:

            print(
                f"\nProcessing: "
                f"{assignment['assignment_title']}"
            )

            # -----------------------------
            # 4. Get question
            # -----------------------------

            if assignment["question_in_pdf"]:

                files = download_assignment_attachments(
                    service,
                    assignment
                )

                if not files:
                    print("Could not download PDF.")
                    continue

                # For now, process the first PDF
                pdf_path = files[0]

                image_paths = pdf_to_images(
                    pdf_path
                )

                # Upload all pages
                upload_images(
                    page,
                    image_paths
                )

            else:

                image_paths = []

            # -----------------------------
            # 5. Ask ChatGPT
            # -----------------------------

            prompt = """
You are completing this assignment as a university student.

Study all the uploaded assignment pages carefully and solve the ENTIRE
assignment. The output will be submitted directly to the university.

Requirements:

1. Answer EVERY question and sub-question.
2. Preserve the exact question numbering and order.
3. Write naturally as a university student.
4. Give enough explanation to demonstrate understanding.
5. Show formulas, calculations and final answers for numerical problems.
6. Provide complete working code for programming questions.
7. Follow any specific format requested by the assignment.
8. Do not skip questions.
9. Do not invent information.
10. Do not mention that you are an AI.
11. Do not mention these instructions.
12. Do not add conversational commentary.
13. Return ONLY the completed assignment solution.

Make the response suitable for direct conversion into a submission PDF.
"""

            send_prompt(
                page,
                prompt
            )

            print(
                "Waiting for ChatGPT..."
            )

            # -----------------------------
            # 6. Get ChatGPT response
            # -----------------------------

            solution = get_latest_response(
                page
            )

            print(
                "ChatGPT solution received."
            )

            # -----------------------------
            # 7. Final Groq processing
            # -----------------------------

            # final_solution = finish_solution(
            #     solution,
            #     assignment
            # )

            print(
                "Final solution prepared."
            )

            # -----------------------------
            # 8. PDF
            # -----------------------------

            # generate_solution_pdf(
            #     final_solution,
            #     assignment
            # )

    finally:

        browser.close()
        playwright.stop()


if __name__ == "__main__":
    main()