from chatgpt_agent import open_chatgpt

playwright, browser, page = open_chatgpt()

input("Press Enter when ready...")

browser.close()
playwright.stop()