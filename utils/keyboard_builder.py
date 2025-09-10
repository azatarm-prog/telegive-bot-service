"""
Inline keyboard builder utilities
Creates Telegram inline keyboards for various interactions
"""

from typing import List, Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def build_participate_keyboard(giveaway_id: int) -> InlineKeyboardMarkup:
    """Build participate button keyboard for giveaway posts"""
    keyboard = [
        [InlineKeyboardButton("🎁 PARTICIPATE", callback_data=f"participate_{giveaway_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_view_results_keyboard(result_token: str) -> InlineKeyboardMarkup:
    """Build VIEW RESULTS button keyboard for conclusion posts"""
    keyboard = [
        [InlineKeyboardButton("🏆 VIEW RESULTS", callback_data=f"view_results_{result_token}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_captcha_keyboard(giveaway_id: int, options: List[str]) -> InlineKeyboardMarkup:
    """Build captcha answer keyboard with multiple choice options"""
    keyboard = []
    for i, option in enumerate(options):
        keyboard.append([
            InlineKeyboardButton(
                option, 
                callback_data=f"captcha_{giveaway_id}_{i}_{option}"
            )
        ])
    return InlineKeyboardMarkup(keyboard)

def build_subscription_check_keyboard(channel_username: str, giveaway_id: int) -> InlineKeyboardMarkup:
    """Build subscription check keyboard"""
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel_username}")],
        [InlineKeyboardButton("✅ I Joined", callback_data=f"check_subscription_{giveaway_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_continue_keyboard(giveaway_id: int, action: str = "continue") -> InlineKeyboardMarkup:
    """Build continue button keyboard"""
    keyboard = [
        [InlineKeyboardButton("✅ Continue", callback_data=f"{action}_{giveaway_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_retry_keyboard(giveaway_id: int, action: str = "retry") -> InlineKeyboardMarkup:
    """Build retry button keyboard"""
    keyboard = [
        [InlineKeyboardButton("🔄 Try Again", callback_data=f"{action}_{giveaway_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_custom_keyboard(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
    """Build custom keyboard from button configuration
    
    Args:
        buttons: List of button rows, each containing button configs with 'text' and 'callback_data' or 'url'
    
    Example:
        buttons = [
            [{"text": "Button 1", "callback_data": "btn1"}, {"text": "Button 2", "url": "https://example.com"}],
            [{"text": "Button 3", "callback_data": "btn3"}]
        ]
    """
    keyboard = []
    for row in buttons:
        keyboard_row = []
        for button_config in row:
            if 'callback_data' in button_config:
                button = InlineKeyboardButton(
                    button_config['text'], 
                    callback_data=button_config['callback_data']
                )
            elif 'url' in button_config:
                button = InlineKeyboardButton(
                    button_config['text'], 
                    url=button_config['url']
                )
            else:
                continue  # Skip invalid button configs
            
            keyboard_row.append(button)
        
        if keyboard_row:  # Only add non-empty rows
            keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(keyboard)

def build_navigation_keyboard(current_page: int, total_pages: int, 
                            callback_prefix: str = "page") -> InlineKeyboardMarkup:
    """Build pagination navigation keyboard"""
    keyboard = []
    
    if total_pages > 1:
        nav_row = []
        
        # Previous button
        if current_page > 1:
            nav_row.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"{callback_prefix}_{current_page - 1}")
            )
        
        # Page indicator
        nav_row.append(
            InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop")
        )
        
        # Next button
        if current_page < total_pages:
            nav_row.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"{callback_prefix}_{current_page + 1}")
            )
        
        keyboard.append(nav_row)
    
    return InlineKeyboardMarkup(keyboard)

def build_confirmation_keyboard(confirm_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """Build confirmation keyboard with Yes/No options"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=confirm_data),
            InlineKeyboardButton("❌ No", callback_data=cancel_data)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_menu_keyboard(menu_items: List[Dict[str, str]], 
                       columns: int = 1) -> InlineKeyboardMarkup:
    """Build menu keyboard with specified number of columns
    
    Args:
        menu_items: List of menu items with 'text' and 'callback_data'
        columns: Number of columns to arrange buttons in
    """
    keyboard = []
    current_row = []
    
    for i, item in enumerate(menu_items):
        current_row.append(
            InlineKeyboardButton(item['text'], callback_data=item['callback_data'])
        )
        
        # Start new row when reaching column limit or at the end
        if len(current_row) == columns or i == len(menu_items) - 1:
            keyboard.append(current_row)
            current_row = []
    
    return InlineKeyboardMarkup(keyboard)

def extract_callback_data(callback_data: str) -> Dict[str, Any]:
    """Extract structured data from callback_data string
    
    Expected format: action_param1_param2_...
    Returns: {'action': 'action', 'params': ['param1', 'param2', ...]}
    """
    parts = callback_data.split('_')
    return {
        'action': parts[0] if parts else '',
        'params': parts[1:] if len(parts) > 1 else []
    }

def build_callback_data(action: str, *params) -> str:
    """Build callback_data string from action and parameters"""
    parts = [action] + [str(param) for param in params]
    return '_'.join(parts)

