"""
CARYDES - Personal AI Assistant
A Telegram bot that connects to local AI models for real-time conversations.

Project Vision:
- Have a personality & soul - more than just code, a genuine companion
- Act as a human-like AI assistant through Telegram
- Remind users of important tasks and information
- Research autonomously on demand
- Run efficiently on consumer GPUs (8-12GB VRAM)

Features:
- Chat with local AI model via Telegram
- Context-aware conversations
- User authentication (whitelist only)
- Chatlog recording
- Input validation and security measures
"""

import logging
import os
import re
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# CONSTANTS
# ============================================

CHATLOG_DIR = 'chatlogs'
LOGS_DIR = 'logs'
DEFAULT_LM_STUDIO_URL = 'http://127.0.0.1:1234'
DEFAULT_MAX_TOKENS = 1000
DEFAULT_MAX_CONVERSATION_HISTORY = 10
DEFAULT_MAX_MESSAGE_LENGTH = 2000
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TIMEOUT = 30
DEFAULT_STATUS_CHECK_TIMEOUT = 5

# Telegram limits
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Rate limiting constants
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_MESSAGES = 10  # max messages per window

# Temperature bounds
TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 2.0

# ============================================
# APPLICATION STATE
# ============================================

class BotState:
    """Application state container for configuration and runtime data.
    
    Uses class variables for singleton-like behavior.
    Thread-safe rate limiting implemented via locks per user.
    """
    config: Dict[str, any] = {}
    conversation_memory: Dict[int, List[Dict[str, str]]] = {}
    user_rate_limits: Dict[int, List[datetime]] = {}
    _rate_limit_locks: Dict[int, asyncio.Lock] = {}
    
    @classmethod
    def get_config(cls) -> Dict[str, any]:
        """Get cached configuration."""
        return cls.config
    
    @classmethod
    def set_config(cls, config: Dict[str, any]) -> None:
        """Set configuration once at startup."""
        cls.config = config
    
    @classmethod
    def get_rate_limit_lock(cls, user_id: int) -> asyncio.Lock:
        """Get or create a lock for rate limiting a specific user."""
        if user_id not in cls._rate_limit_locks:
            cls._rate_limit_locks[user_id] = asyncio.Lock()
        return cls._rate_limit_locks[user_id]
    
    @classmethod
    def clear_all(cls) -> None:
        """Clear all state (for testing or reset)."""
        cls.config = {}
        cls.conversation_memory = {}
        cls.user_rate_limits = {}
        cls._rate_limit_locks = {}


# ============================================
# CONFIGURATION
# ============================================

class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


def load_config() -> Dict[str, any]:
    """
    Load configuration from environment variables (.env file).
    
    Raises:
        ConfigurationError: If required configuration is missing or invalid.
    """
    config = {}
    
    # Required: Telegram Bot Token
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not telegram_bot_token:
        raise ConfigurationError(
            "TELEGRAM_BOT_TOKEN not found in environment variables. "
            "Please set it in your .env file."
        )
    config['telegram_bot_token'] = telegram_bot_token
    
    # Required: User Whitelist (at least one user must be specified)
    user_whitelist = _parse_list_env('USER_WHITELIST')
    if not user_whitelist:
        raise ConfigurationError(
            "USER_WHITELIST is required. "
            "Please add at least one Telegram user ID to USER_WHITELIST in your .env file. "
            "Format: USER_WHITELIST=123456789,987654321"
        )
    config['user_whitelist'] = user_whitelist
    logger.info(f"Whitelisted users: {len(user_whitelist)} user(s)")
    
    # LM Studio URL with validation
    lm_studio_url = os.getenv('LM_STUDIO_URL', DEFAULT_LM_STUDIO_URL)
    if not _validate_lm_studio_url(lm_studio_url):
        raise ConfigurationError(
            f"Invalid LM_STUDIO_URL: {lm_studio_url}. "
            "URL must be a valid localhost address (http://127.0.0.1 or http://localhost)."
        )
    config['lm_studio_url'] = lm_studio_url
    
    # Load optional configuration with type coercion and validation
    config['max_tokens'] = _parse_int_env('MAX_TOKENS', DEFAULT_MAX_TOKENS)
    config['max_conversation_history'] = _parse_int_env('MAX_CONVERSATION_HISTORY', DEFAULT_MAX_CONVERSATION_HISTORY)
    config['max_message_length'] = _parse_int_env('MAX_MESSAGE_LENGTH', DEFAULT_MAX_MESSAGE_LENGTH)
    config['temperature'] = _parse_temperature_env('TEMPERATURE', DEFAULT_TEMPERATURE)
    config['log_level'] = os.getenv('LOG_LEVEL', 'INFO')
    config['log_to_file'] = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
    config['log_file_path'] = os.getenv('LOG_FILE_PATH', 'logs/bot.log')
    
    return config


def _validate_lm_studio_url(url: str) -> bool:
    """Validate that LM Studio URL is a safe localhost address.
    
    Prevents SSRF attacks by only allowing localhost addresses.
    """
    if not url:
        return False
    
    # Normalize URL for comparison
    url_lower = url.lower().strip()
    
    # Allowed localhost patterns
    allowed_patterns = [
        'http://127.0.0.1',
        'http://localhost',
        'https://127.0.0.1',
        'https://localhost',
    ]
    
    return any(url_lower.startswith(pattern) for pattern in allowed_patterns)


def _parse_list_env(key: str) -> List[str]:
    """Parse a comma-separated environment variable into a list."""
    value = os.getenv(key, '')
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def _parse_int_env(key: str, default: int) -> int:
    """Parse an integer environment variable with fallback."""
    try:
        value = os.getenv(key)
        if value is None:
            return default
        result = int(value)
        if result < 0:
            logger.warning(f"Negative value for {key}, using default: {default}")
            return default
        return result
    except ValueError:
        logger.warning(f"Invalid value for {key}, using default: {default}")
        return default


def _parse_float_env(key: str, default: float, min_val: float = None, max_val: float = None) -> float:
    """Parse a float environment variable with fallback and bounds checking."""
    try:
        value = os.getenv(key)
        if value is None:
            return default
        result = float(value)
        if min_val is not None and result < min_val:
            logger.warning(f"Value for {key} below minimum ({min_val}), using default: {default}")
            return default
        if max_val is not None and result > max_val:
            logger.warning(f"Value for {key} above maximum ({max_val}), using default: {default}")
            return default
        return result
    except ValueError:
        logger.warning(f"Invalid value for {key}, using default: {default}")
        return default


def _parse_temperature_env(key: str, default: float) -> float:
    """Parse temperature with validation (must be between 0.0 and 2.0)."""
    return _parse_float_env(key, default, TEMPERATURE_MIN, TEMPERATURE_MAX)


# ============================================
# DIRECTORY MANAGEMENT
# ============================================

def setup_directories() -> None:
    """Create necessary directories for chatlogs and logs."""
    for directory in [CHATLOG_DIR, LOGS_DIR]:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
        except OSError as e:
            logger.error(f"Error creating directory {directory}: {e}")
            raise


# ============================================
# CHATLOG MANAGEMENT
# ============================================

def log_message(user_id: int, role: str, message: str) -> bool:
    """Log a message to the user's chatlog file.
    
    Args:
        user_id: Telegram user ID
        role: 'user', 'assistant', or 'system'
        message: The message content
        
    Returns:
        True if logged successfully, False otherwise
    """
    try:
        # Sanitize user_id to prevent path traversal
        safe_user_id = re.sub(r'[^0-9]', '', str(user_id))
        if not safe_user_id:
            logger.warning(f"Invalid user_id for logging: {user_id}")
            return False
            
        user_dir = os.path.join(CHATLOG_DIR, safe_user_id)
        os.makedirs(user_dir, exist_ok=True)
        
        # Create log file with date
        date_str = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(user_dir, f'{date_str}.txt')
        
        # Get current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Sanitize message content to prevent log injection
        safe_message = _sanitize_for_log(message)
        
        # Log the message
        log_entry = f"[{timestamp}] [{role}] {safe_message}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
            
        logger.debug(f"Logged message for user {user_id}: [{role}]")
        return True
    except Exception as e:
        logger.error(f"Error logging message: {e}")
        return False


def _sanitize_for_log(message: str) -> str:
    """Sanitize message for safe logging (prevent log injection)."""
    if not message:
        return ""
    # Remove newlines and carriage returns to prevent log injection
    return message.replace('\n', '\\n').replace('\r', '\\r')


# ============================================
# SECURITY FUNCTIONS
# ============================================

def is_user_allowed(user_id: int, config: Dict[str, any]) -> bool:
    """Check if user is allowed to use the bot.
    
    Args:
        user_id: Telegram user ID
        config: Configuration dictionary
        
    Returns:
        True if user is in the whitelist, False otherwise
    """
    user_whitelist = config.get('user_whitelist', [])
    
    # Whitelist is required - if empty, deny access (shouldn't happen due to config validation)
    if not user_whitelist:
        logger.error("USER_WHITELIST is empty - denying all access")
        return False
    
    allowed = str(user_id) in user_whitelist
    
    if not allowed:
        logger.warning(f"Unauthorized access attempt by user {user_id}")
    
    return allowed


async def check_rate_limit(user_id: int) -> bool:
    """Check if user has exceeded rate limit (thread-safe).
    
    Uses per-user locks to prevent race conditions.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if user is under rate limit, False if exceeded
    """
    lock = BotState.get_rate_limit_lock(user_id)
    
    async with lock:
        now = datetime.now()
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
        
        # Get user's message timestamps
        user_timestamps = BotState.user_rate_limits.get(user_id, [])
        
        # Filter to only recent messages within the window
        recent_timestamps = [ts for ts in user_timestamps if ts > window_start]
        
        # Check if under limit
        if len(recent_timestamps) >= RATE_LIMIT_MAX_MESSAGES:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False
        
        # Add current timestamp
        recent_timestamps.append(now)
        BotState.user_rate_limits[user_id] = recent_timestamps
        
        return True


def sanitize_input(text: str, max_length: int = 4000) -> str:
    """Sanitize user input to prevent injection attacks.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes and control characters (except newlines/tabs)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Truncate to max length
    sanitized = sanitized[:max_length]
    
    return sanitized.strip()


def sanitize_for_lm_studio(text: str) -> str:
    """Sanitize input specifically for LM Studio API.
    
    Removes potential prompt injection attempts.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text safe for API submission
    """
    if not text:
        return ""
    
    # Remove potential system prompt injection attempts
    patterns_to_block = [
        r'^/system\s*:?\s*',
        r'^/prompt\s*:?\s*',
        r'^\[system\]',
        r'^(system|assistant|user)\s*:\s*',
    ]
    
    sanitized = text
    for pattern in patterns_to_block:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')
    
    # Truncate to reasonable length
    return sanitized[:4000]


def chunk_message(message: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """Split a message into chunks that fit within Telegram's limits.
    
    Args:
        message: The message to chunk
        max_length: Maximum length per chunk (default: Telegram's limit)
        
    Returns:
        List of message chunks
    """
    if len(message) <= max_length:
        return [message]
    
    chunks = []
    # Try to break on newlines or spaces for cleaner splits
    remaining = message
    
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
            
        # Find a good break point
        break_point = max_length
        for i in range(max_length - 1, max(0, max_length - 200), -1):
            if remaining[i] in '\n .,!?;:':
                break_point = i + 1
                break
        
        chunks.append(remaining[:break_point])
        remaining = remaining[break_point:]
    
    return chunks


# ============================================
# CONVERSATION MEMORY
# ============================================

def get_conversation_history(user_id: int, max_history: int) -> List[Dict[str, str]]:
    """Get conversation history for a user.
    
    Args:
        user_id: Telegram user ID
        max_history: Maximum number of messages to return
        
    Returns:
        List of message dictionaries with 'role' and 'content'
    """
    history = BotState.conversation_memory.get(user_id, [])
    return history[-max_history:] if max_history > 0 else []


def update_conversation_history(user_id: int, user_message: str, ai_response: str, max_history: int) -> None:
    """Update conversation history for a user.
    
    Args:
        user_id: Telegram user ID
        user_message: User's message
        ai_response: AI's response
        max_history: Maximum history to keep
    """
    if max_history <= 0:
        return
        
    current_history = BotState.conversation_memory.get(user_id, [])
    
    # Add new messages
    current_history.extend([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": ai_response}
    ])
    
    # Trim to max history
    BotState.conversation_memory[user_id] = current_history[-max_history:]


def clear_conversation_memory(user_id: int) -> None:
    """Clear conversation memory for a specific user.
    
    Args:
        user_id: Telegram user ID
    """
    if user_id in BotState.conversation_memory:
        BotState.conversation_memory[user_id] = []
        logger.info(f"Cleared conversation memory for user {user_id}")


# ============================================
# LM STUDIO API
# ============================================

async def check_lm_studio_status(session: aiohttp.ClientSession, url: str) -> bool:
    """Check if LM Studio is running and responding.
    
    Args:
        session: aiohttp client session
        url: LM Studio server URL
        
    Returns:
        True if LM Studio is responding, False otherwise
    """
    try:
        async with session.get(
            f"{url}/v1/models",
            timeout=aiohttp.ClientTimeout(total=DEFAULT_STATUS_CHECK_TIMEOUT)
        ) as response:
            return response.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


async def send_to_lm_studio(
    session: aiohttp.ClientSession,
    message: str,
    user_id: int,
    config: Dict[str, any],
    max_retries: int = 2
) -> Tuple[bool, str]:
    """Send message to LM Studio and get response asynchronously.
    
    Implements retry logic for transient failures.
    
    Args:
        session: aiohttp client session
        message: User's message
        user_id: Telegram user ID
        config: Configuration dictionary
        max_retries: Number of retry attempts for transient failures
        
    Returns:
        Tuple of (success: bool, response: str)
    """
    try:
        # Validate and sanitize message length
        max_length = config.get('max_message_length', DEFAULT_MAX_MESSAGE_LENGTH)
        if len(message) > max_length:
            return (False, f"❌ Message too long. Maximum length is {max_length} characters.")
        
        # Sanitize input for security
        safe_message = sanitize_for_lm_studio(message)
        
        # Prepare conversation context
        max_history = config.get('max_conversation_history', DEFAULT_MAX_CONVERSATION_HISTORY)
        history = get_conversation_history(user_id, max_history)
        
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant. Provide concise and accurate responses."}
        ]
        
        # Add conversation history
        messages.extend(history)
        
        # Add current message
        messages.append({"role": "user", "content": safe_message})
        
        # Call LM Studio API with retry logic
        lm_studio_url = config['lm_studio_url']
        timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
        max_tokens = config.get('max_tokens', DEFAULT_MAX_TOKENS)
        temperature = config.get('temperature', DEFAULT_TEMPERATURE)
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                async with session.post(
                    f"{lm_studio_url}/v1/chat/completions",
                    json={
                        "model": "local-model",
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Validate response structure
                        if 'choices' not in data or not data['choices']:
                            return (False, "❌ Invalid response from LM Studio.")
                        
                        ai_response = data['choices'][0].get('message', {}).get('content', '')
                        
                        if not ai_response:
                            return (False, "❌ Empty response from LM Studio.")
                        
                        # Update conversation memory
                        update_conversation_history(user_id, safe_message, ai_response, max_history)
                        
                        return (True, ai_response)
                    
                    elif response.status >= 500 and attempt < max_retries:
                        # Retry on server errors
                        logger.warning(f"LM Studio server error {response.status}, retrying (attempt {attempt + 1})")
                        await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        # Log error but don't expose details to user
                        error_text = await response.text()
                        logger.error(f"LM Studio error {response.status}: {error_text[:200]}")
                        return (False, "❌ Error from AI service. Please try again.")
                        
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    logger.warning(f"Request timeout, retrying (attempt {attempt + 1})")
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                logger.warning(f"Request timeout for user {user_id}")
                return (False, "⏱️ Request timed out. The AI might be processing a long response.")
                
            except aiohttp.ClientError as e:
                if attempt < max_retries:
                    logger.warning(f"Connection error, retrying (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                last_error = e
                break
        
        # All retries exhausted
        logger.error(f"Connection error for user {user_id}: {last_error}")
        return (False, "❌ Cannot connect to AI service. Please ensure it's running.")
        
    except Exception as e:
        logger.error(f"Unexpected error for user {user_id}: {e}")
        return (False, "❌ An unexpected error occurred. Please try again.")


# ============================================
# COMMAND HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = (
        "👋 Hello! I'm **CARYDES**, your personal AI assistant.\n\n"
        "I can help you with tasks, remind you of things, and have natural conversations. "
        "Just send me a message!\n\n"
        "**Commands:**\n"
        "/start - Start CARYDES\n"
        "/help - Show this help message\n"
        "/new - Start a new conversation (saves previous)\n"
        "/reset - Clear conversation context\n"
        "/status - Check AI service status"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_message = (
        "🤖 **Help Guide**\n\n"
        "I'm your personal AI assistant powered by a local AI model.\n\n"
        "**Usage:**\n"
        "Simply send me any message and I'll respond.\n\n"
        "**Commands:**\n"
        "/start - Start CARYDES\n"
        "/help - Show this help message\n"
        "/new - Start a new conversation (saves previous context)\n"
        "/reset - Clear conversation context (no save)\n"
        "/status - Check AI service status"
    )
    await update.message.reply_text(help_message, parse_mode='Markdown')


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command - Start a new conversation with logging."""
    user_id = update.effective_user.id
    
    # Log the session boundary
    log_message(user_id, 'system', '--- NEW SESSION STARTED ---')
    
    # Clear conversation memory
    clear_conversation_memory(user_id)
    
    await update.message.reply_text("✅ Starting a new conversation. Previous context has been saved.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command - Clear context without logging."""
    user_id = update.effective_user.id
    clear_conversation_memory(user_id)
    await update.message.reply_text("✅ Conversation context has been reset.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    config = BotState.get_config()
    lm_studio_url = config.get('lm_studio_url', DEFAULT_LM_STUDIO_URL)
    
    try:
        async with aiohttp.ClientSession() as session:
            if await check_lm_studio_status(session, lm_studio_url):
                await update.message.reply_text("✅ LM Studio is running and responding.")
            else:
                await update.message.reply_text("⚠️ LM Studio is running but not responding correctly.")
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        await update.message.reply_text("❌ Error checking status. Please try again.")


# ============================================
# MESSAGE HANDLER
# ============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Ignore commands
    if user_message.startswith('/'):
        return
    
    config = BotState.get_config()
    
    # Check authorization (whitelist only)
    if not is_user_allowed(user_id, config):
        logger.warning(f"Unauthorized user {user_id} attempted to use bot")
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    
    # Check rate limit (async, thread-safe)
    if not await check_rate_limit(user_id):
        await update.message.reply_text("⏳ Too many messages. Please wait a moment.")
        return
    
    # Sanitize and validate input
    sanitized_message = sanitize_input(user_message, config.get('max_message_length', DEFAULT_MAX_MESSAGE_LENGTH))
    if not sanitized_message:
        await update.message.reply_text("❌ Invalid message.")
        return
    
    # Log user message
    log_message(user_id, 'user', sanitized_message)
    
    # Send typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Get response from LM Studio asynchronously
    try:
        async with aiohttp.ClientSession() as session:
            success, ai_response = await send_to_lm_studio(session, sanitized_message, user_id, config)
    except Exception as e:
        logger.error(f"Error in LM Studio communication: {e}")
        await update.message.reply_text("❌ Error communicating with AI. Please try again.")
        return
    
    # Log bot response
    log_message(user_id, 'assistant', ai_response)
    
    # Send response back to user (handle long messages)
    chunks = chunk_message(ai_response)
    for chunk in chunks:
        await update.message.reply_text(chunk)


# ============================================
# ERROR HANDLERS
# ============================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the dispatcher."""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.message:
        await update.message.reply_text(
            "⚠️ An unexpected error occurred. Please try again later."
        )


# ============================================
# GRACEFUL SHUTDOWN
# ============================================

def setup_graceful_shutdown(application: Application) -> None:
    """Setup graceful shutdown handlers."""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        print("\n🛑 Shutting down gracefully...")
        
        # Stop the application
        if application.running:
            asyncio.create_task(application.stop())
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


# ============================================
# MAIN ENTRY POINT
# ============================================

def main() -> None:
    """Main entry point for the bot."""
    try:
        # Load configuration ONCE at startup
        config = load_config()
        BotState.set_config(config)
        
        # Set log level from config
        log_level = getattr(logging, config.get('log_level', 'INFO').upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)
        
        logger.info("Configuration loaded successfully")
        logger.info(f"LM Studio URL: {config['lm_studio_url']}")
        logger.info(f"Allowed users: {len(config['user_whitelist'])}")
        
        # Setup directories
        setup_directories()
        
        # Create the application
        application = Application.builder().token(config['telegram_bot_token']).build()
        
        # Setup graceful shutdown
        setup_graceful_shutdown(application)
        
        # Register command handlers
        _register_command_handlers(application)
        
        # Register message handler
        _register_message_handlers(application)
        
        # Register error handler
        application.add_error_handler(error_handler)
        
        # Start CARYDES
        logger.info("Starting CARYDES...")
        print("🚀 CARYDES is starting... Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease check your .env file and ensure all required variables are set:")
        print("  - TELEGRAM_BOT_TOKEN (required)")
        print("  - USER_WHITELIST (required - at least one user ID)")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"\n❌ Error: {e}")


def _register_command_handlers(application: Application) -> None:
    """Register all command handlers."""
    commands = [
        ("start", start_command),
        ("help", help_command),
        ("new", new_command),
        ("reset", reset_command),
        ("status", status_command),
    ]
    
    for command, handler in commands:
        application.add_handler(CommandHandler(command, handler))
        logger.debug(f"Registered command: /{command}")


def _register_message_handlers(application: Application) -> None:
    """Register message handlers."""
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    logger.debug("Registered message handler")


if __name__ == "__main__":
    main()