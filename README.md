# CARYDES

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Early%20Development-orange)

**CARYDES** is a personal AI assistant that runs locally on consumer-grade hardware. Designed to work efficiently with language models on 8-12GB VRAM GPUs.

> ⚠️ **Note**: This project is under development and in an early stage.

## 🎯 Project Vision

CARYDES aims to be a human-like AI assistant that can:

- ✨ **Have a personality & soul** - More than just code, a genuine companion with character
- 💭 **Remind you of things** - Never forget important tasks or information
- 🔍 **Research autonomously** - Search and gather information on demand  
- 💬 **Act as your assistant** - Natural conversation through Telegram
- 🖥️ **Run efficiently on your machine** - Optimized for consumer GPUs (8-12GB VRAM)

## 📑 Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Commands](#commands)
- [Security](#security)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

---

## Features

- 🤖 **Chat with AI** - Interact with your local LM Studio model via Telegram
- 💬 **Context-Aware** - Remembers conversation history for coherent responses
- 🔐 **Access Control** - Whitelist-only access for security
- 📝 **Chatlog Recording** - Automatic logging of all conversations
- 🛡️ **Security Hardened** - Input validation, rate limiting, SSRF protection
- ⚡ **Async Architecture** - Non-blocking operations for better performance

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/CARYDES.git
cd CARYDES

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure the bot
cp .env.example .env
# Edit .env and add your TELEGRAM_BOT_TOKEN and USER_WHITELIST

# 5. Run CARYDES
python main.py
```

---

## Installation

### Prerequisites

| Requirement | Description |
|-------------|-------------|
| Python 3.7+ | Required for running CARYDES |
| LM Studio | Running locally with a model loaded |
| Telegram Bot Token | Get from [@BotFather](https://t.me/BotFather) |
| GPU (Optional) | 8-12GB VRAM recommended for local LLMs |

### Step-by-Step Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/CARYDES.git
cd CARYDES
```

#### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the token provided

#### 5. Get Your Telegram User ID

1. Open Telegram and search for **@userinfobot**
2. Send any message
3. It will reply with your Telegram user ID

#### 6. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
USER_WHITELIST=your_telegram_user_id

# Optional (defaults shown)
LM_STUDIO_URL=http://127.0.0.1:1234
MAX_TOKENS=1000
TEMPERATURE=0.7
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | - | Your Telegram bot token from @BotFather |
| `USER_WHITELIST` | ✅ Yes | - | Comma-separated user IDs allowed to use bot |
| `LM_STUDIO_URL` | No | `http://127.0.0.1:1234` | LM Studio server URL (localhost only) |
| `MAX_TOKENS` | No | `1000` | Maximum tokens in AI response |
| `MAX_MESSAGE_LENGTH` | No | `2000` | Maximum user message length |
| `MAX_CONVERSATION_HISTORY` | No | `10` | Messages to remember per user |
| `TEMPERATURE` | No | `0.7` | AI creativity (0.0-2.0) |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_TO_FILE` | No | `true` | Enable file logging |

### User Whitelist Setup

```env
# Add your Telegram user ID (required)
# Find your ID by messaging @userinfobot on Telegram
USER_WHITELIST=123456789

# Multiple users (comma-separated)
USER_WHITELIST=123456789,987654321
```

> **Important**: The bot will NOT start if USER_WHITELIST is empty. This is a security feature to prevent unauthorized access.

---

## Usage

### Starting CARYDES

**Using the quick start script:**
```bash
chmod +x run.sh
./run.sh
```

**Manual start:**
```bash
source venv/bin/activate
python main.py
```

### Stopping CARYDES

Press `Ctrl+C` in the terminal where the bot is running. The bot handles graceful shutdown automatically.

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start CARYDES and see welcome message |
| `/help` | Show help information |
| `/new` | Start a new conversation (saves previous context to logs) |
| `/reset` | Clear conversation context (no logging) |
| `/status` | Check AI service connection status |

### /new vs /reset

- **`/new`** - Logs a session boundary marker and clears context. Use this when starting a fresh topic while keeping a record.
- **`/reset`** - Simply clears the conversation context without any logging. Quick reset without record.

---

## Security

### Built-in Security Features

| Feature | Protection Against |
|---------|-------------------|
| Whitelist Only | Unauthorized access - only specified users can interact |
| URL Validation | SSRF attacks (only localhost allowed) |
| Input Sanitization | Injection attacks, control characters |
| Rate Limiting | Spam/abuse (10 messages/minute) |
| Prompt Filtering | AI prompt injection |
| Path Traversal Protection | Unauthorized file access |
| Log Sanitization | Log injection attacks |

### Security Best Practices

1. **Keep USER_WHITELIST limited** - Only add users you trust
2. **Never commit `.env`** - It's in `.gitignore` for a reason
3. **Monitor logs** - Check for suspicious activity
4. **Keep dependencies updated** - Run `pip install --upgrade -r requirements.txt`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        TELEGRAM                             │
│                         API                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   CARYDES (main.py)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Command   │  │   Message   │  │   Security Layer    │  │
│  │  Handlers   │  │   Handler   │  │ • Rate Limiting     │  │
│  │             │  │             │  │ • Input Sanitization│  │
│  │ /start      │  │ (text in)   │  │ • Whitelist Check   │  │
│  │ /help       │  │             │  │ • URL Validation    │  │
│  │ /new        │  └──────┬──────┘  └──────────┬──────────┘  │
│  │ /reset      │         │                    │             │
│  │ /status     │         ▼                    │             │
│  └─────────────┘  ┌─────────────┐             │             │
│                   │  LM Studio  │◄────────────┘             │
│                   │    API      │                           │
│                   │ (OpenAI-    │                           │
│                   │ compatible) │                           │
│                   └──────┬──────┘                           │
│                          │                                  │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │                    BotState                           │  │
│  │  • Config          • Conversation Memory              │  │
│  │  • Rate Limits     • User Locks                       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Local Storage                            │
│  ┌──────────────────┐              ┌─────────────┐          │
│  │  chatlogs/       │              │   logs/     │          │
│  │  /[user_id]      │              │  bot.log    │          │
│  │  /YYYY-MM-DD.txt │              └─────────────┘          │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. User sends message → Telegram API
2. Telegram API → CARYDES (webhook/polling)
3. CARYDES checks whitelist authorization
4. CARYDES validates & sanitizes input
5. CARYDES checks rate limits
6. CARYDES sends to LM Studio API
7. LM Studio responds
8. CARYDES logs conversation
9. CARYDES sends response to user

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Bot won't start | Ensure TELEGRAM_BOT_TOKEN and USER_WHITELIST are set in `.env` |
| "Configuration Error" | Check that USER_WHITELIST has at least one user ID |
| Bot not responding | Verify LM Studio is running with a model loaded |
| Connection errors | Check `LM_STUDIO_URL` in `.env` |
| "You are not authorized" | Add your user ID to `USER_WHITELIST` |
| Long response times | Reduce `MAX_TOKENS` or `MAX_CONVERSATION_HISTORY` |
| Rate limit errors | Wait 60 seconds before sending more messages |

### Debug Mode

Enable debug logging for more details:

```env
LOG_LEVEL=DEBUG
```

### Getting Help

1. Check logs in `logs/bot.log`
2. Verify your `.env` configuration
3. Ensure LM Studio API is accessible at the configured URL
4. Try restarting both LM Studio and CARYDES

---

## Contributing

Contributions are welcome! Here's how to help:

### Reporting Issues

1. Check existing issues to avoid duplicates
2. Include steps to reproduce
3. Include error messages and logs (remove sensitive data)

### Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Code Style

- Follow PEP 8 for Python code
- Add docstrings for new functions
- Update documentation for new features

---

## Changelog

### [0.1.0] - 2026-02-20

**Created**
- Currently just an AI chatbot that connects to your telegram bot. 

---

## License

This project is open source and available under the MIT License.

---

## Project Structure

```
.
├── .env.example          # Environment variable template
├── .gitignore            # Git ignore rules
├── main.py               # Main CARYDES logic
├── requirements.txt      # Python dependencies
├── run.sh                # Quick start script
├── backup_chatlogs.sh    # Backup script
├── README.md             # This file
├── chatlogs/             # Conversation logs (git-ignored)
└── logs/                 # Bot logs (git-ignored)