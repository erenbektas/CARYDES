#!/bin/bash

# Telegram LM Studio Bot - Quick Start Script

echo "🚀 Starting Telegram LM Studio Bot..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7+ first."
    exit 1
fi

# Check if .env file exists, if not create from .env.example
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📦 Creating .env file from .env.example..."
        cp .env.example .env
        echo "⚠️  Please edit .env file and add your actual configuration values"
        echo "   Get your Telegram bot token from @BotFather on Telegram"
    else
        echo "❌ .env.example not found. Please create a .env file with your configuration."
        exit 1
    fi
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found."
    exit 1
fi

# Create chatlogs directory if it doesn't exist
if [ ! -d "chatlogs" ]; then
    mkdir -p chatlogs
    echo "📦 Created chatlogs directory"
fi

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo "📦 Created logs directory"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
echo "📦 Checking dependencies..."
pip install -r requirements.txt

# Check if bot token is configured
if grep -q "YOUR_BOT_TOKEN_HERE" .env; then
    echo "⚠️  Warning: Please update TELEGRAM_BOT_TOKEN in .env file"
    echo "   Get your token from @BotFather on Telegram"
fi

# Start the bot
echo ""
echo "✅ Starting bot..."
python main.py
