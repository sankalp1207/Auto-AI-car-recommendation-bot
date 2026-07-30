import base64
import json
import re
from typing import Any
from telegram import Update
from telegram.ext import CallbackContext

def escape_markdown_v2(text: Any) -> str:
    """
    Escapes all special characters for Telegram's MarkdownV2 format.
    Should be applied to variables before combining them with formatting syntax.
    """
    if text is None:
        return ""
    text_str = str(text)
    # Characters that must be escaped in MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{char}" if char in escape_chars else char for char in text_str)

def parse_budget(text: str) -> int:
    """
    Converts user budget input to integer Rupees.
    Supports formats like: "15", "15.5 Lakhs", "15L", "1,500,000", "₹1200000".
    If budget <= 150, treats it as Lakhs and multiplies by 100,000.
    """
    cleaned = text.strip().lower()
    # Remove currency symbol and commas
    cleaned = cleaned.replace("₹", "").replace(",", "")
    
    # Check if 'lakh' or 'l' is in the text
    is_lakh = "lakh" in cleaned or "l" in cleaned or re.search(r'\b\d+(\.\d+)?\s*l\b', cleaned)
    
    # Extract numeric value
    match = re.search(r'\d+(\.\d+)?', cleaned)
    if not match:
        raise ValueError("Could not parse budget. Please enter a valid number.")
        
    val = float(match.group(0))
    
    # If the user specified Lakhs, or entered a value <= 150 (assuming Lakhs)
    if is_lakh or val <= 150:
        return int(val * 100_000)
    else:
        return int(val)

def decode_user_id_from_token(token: str) -> int:
    """
    Decodes the user ID ('sub') from the backend JWT access token.
    Safe extraction without signature verification, since we trust the backend.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        payload_b64 = parts[1]
        # Add base64 padding if necessary
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        
        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)
        return int(payload.get("sub"))
    except Exception as e:
        # Fallback if parsing fails
        raise ValueError(f"Failed to decode token payload: {e}")

async def send_typing_action(update: Update, context: CallbackContext):
    """
    Sends a 'typing' chat action to Telegram.
    """
    if update.effective_chat:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

def markdown_to_html(md_text: str) -> str:
    """
    Converts simple Markdown strings to Telegram-safe HTML strings.
    """
    if not md_text:
        return ""
    # Escape HTML special characters
    html = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert bold **text** to <b>text</b>
    html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
    # Convert italic *text* or _text_ to <i>text</i>
    # Avoid matching the HTML tags we just introduced
    html = re.sub(r'(?<!\<)\*(.*?)\*(?!\>)', r'<i>\1</i>', html)
    html = re.sub(r'(?<!\<)_(.*?)(?!\>)', r'<i>\1</i>', html)
    # Convert `code` to <code>code</code>
    html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
    # Convert headers (e.g., ### Header) to bold lines
    lines = []
    for line in html.split("\n"):
        if line.startswith("#"):
            line = re.sub(r'^#+\s*(.*)$', r'<b>\1</b>', line)
        lines.append(line)
    return "\n".join(lines)

