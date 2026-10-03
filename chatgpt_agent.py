from playwright.sync_api import sync_playwright


def open_chatgpt():
    playwright = sync_playwright().start()

    browser = playwright.chromium.launch(
        headless=False
    )

    page = browser.new_page()

    page.goto("https://chatgpt.com/")
    page.wait_for_load_state("domcontentloaded")

    return playwright, browser, page


def upload_images(page, image_paths):
    print("uploading images")
    file_input = page.locator(
        "#octane-mobile-composer-photos-input"
    )

    file_input.set_input_files(image_paths)


def send_prompt(page, prompt):
    textbox = page.get_by_role("textbox")

    textbox.fill(prompt)

    send_button = page.get_by_role(
        "button",
        name="Send message"
    )

    send_button.click()


def get_latest_response(page):
    # Wait for ChatGPT to generate something
    page.wait_for_timeout(3000)

    # Wait until an assistant message exists
    response = page.locator(
        '[data-message-author-role="assistant"]'
    ).last

    response.wait_for()

    return response.inner_text()

def inspect_page(page):
    print("\nTEXTAREAS:")
    print(page.locator("textarea").count())

    print("\nCONTENTEDITABLE:")
    print(page.locator('[contenteditable="true"]').count())

    print("\nTEXTBOX ROLE:")
    print(page.get_by_role("textbox").count())

    print("\nBUTTONS:")
    for i in range(min(page.get_by_role("button").count(), 30)):
        button = page.get_by_role("button").nth(i)
        try:
            print(
                i,
                repr(button.inner_text()),
                button.get_attribute("aria-label")
            )
        except:
            pass