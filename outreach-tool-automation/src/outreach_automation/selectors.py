INSTAGRAM_MESSAGE_BUTTONS = [
    "button:has-text('Message')",
    "a:has-text('Message')",
    "[role='button']:has-text('Message')",
]

INSTAGRAM_DM_INPUTS = [
    "div[contenteditable='true'][role='textbox']",
    "[role='textbox'][contenteditable='true']",
    "[contenteditable='true'][aria-label='Message']",
    "textarea",
]

INSTAGRAM_INBOX_SEARCH_INPUTS = [
    "input[placeholder='Search']",
    "input[aria-label='Search']",
]

INSTAGRAM_THREAD_ROWS = [
    "div[role='button']",
]

TIKTOK_MESSAGE_BUTTONS = [
    "button:has-text('Message')",
    "a:has-text('Message')",
]

TIKTOK_DM_INPUTS = [
    "[data-e2e='chat-input'] div[contenteditable='true']",
    "[data-e2e='message-input-area'] div[contenteditable='true']",
    "div[contenteditable='true'][role='textbox']",
    "div[contenteditable='true']",
    "textarea[placeholder*='message' i]",
    "textarea",
]

TIKTOK_SEND_BUTTONS = [
    "button[data-e2e='message-send']",
    "button[aria-label='Send']",
    "button:has-text('Send')",
]
