from chatgpt_agent import open_chatgpt

IMAGE_PATH = "pdf_pages/page_1.png"

playwright, browser, page = open_chatgpt()

page.wait_for_timeout(3000)

# ChatGPT's image upload input
file_input = page.locator("#octane-mobile-composer-photos-input")

print("Image inputs found:", file_input.count())

file_input.set_input_files(IMAGE_PATH)

print("Image uploaded.")

input("Press Enter to close...")

browser.close()
playwright.stop()