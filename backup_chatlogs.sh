#!/bin/bash

# Telegram LM Studio Bot - Chatlogs Backup Script

BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
CHATLOGS_DIR="chatlogs"

# Create backup directory if it doesn't exist
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    echo "📦 Created backup directory: $BACKUP_DIR"
fi

# Create backup archive
if [ -d "$CHATLOGS_DIR" ]; then
    tar -czf "$BACKUP_DIR/chatlogs_backup_$DATE.tar.gz" -C "$CHATLOGS_DIR" .
    echo "✅ Chatlogs backed up to: $BACKUP_DIR/chatlogs_backup_$DATE.tar.gz"
else
    echo "⚠️  Chatlogs directory not found. Nothing to backup."
fi

# Keep only the last 7 backups
echo "🧹 Cleaning up old backups..."
find "$BACKUP_DIR" -name "chatlogs_backup_*.tar.gz" -type f -mtime +7 -delete
echo "✅ Old backups cleaned up (older than 7 days)"