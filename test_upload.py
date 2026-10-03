from chatgpt_agent import open_chatgpt

PDF_PATH = "downloads/Computer_Networks_Assignment.pdf"

playwright, browser, page = open_chatgpt()

page.wait_for_timeout(3000)

# Find the file input
file_input = page.locator("#octane-mobile-composer-files-input")
print("File inputs found:", file_input.count())

file_input.set_input_files(PDF_PATH)

print("PDF uploaded.")

input("Press Enter to close...")

browser.close()
playwright.stop()