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
    "input[placeholder*='send a message' i]",
    "input[placeholder*='message' i]",
    "input[aria-label*='message' i]",
    "[data-e2e='chat-input'] div[contenteditable='true']",
    "[data-e2e='message-input-area'] div[contenteditable='true']",
    "[data-e2e='message-input-area'] [contenteditable='plaintext-only']",
    "[data-e2e='chat-input'] [contenteditable='plaintext-only']",
    "[data-e2e*='chat-input'] [contenteditable]",
    "[data-e2e*='message-input'] [contenteditable]",
    "div[role='textbox'][contenteditable='true']",
    "div[role='textbox'][contenteditable='plaintext-only']",
    "div[aria-label*='message' i][contenteditable]",
    "div[contenteditable='true'][role='textbox']",
    "div[contenteditable='plaintext-only'][role='textbox']",
    "div[contenteditable='true']",
    "div[contenteditable='plaintext-only']",
    "textarea[placeholder*='message' i]",
    "textarea",
]

TIKTOK_SEND_BUTTONS = [
    "button[data-e2e='message-send']",
    "button[aria-label='Send']",
    "button:has-text('Send')",
]
