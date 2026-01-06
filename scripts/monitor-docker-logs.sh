#!/bin/bash

# Monitor Docker Compose logs for idle periods and send Telegram notifications
# Usage: ./monitor-docker-logs.sh [PROJECT_DIR] [IDLE_TIMEOUT_SECONDS]

set -euo pipefail

# Default values
PROJECT_DIR="${1:-.}"
IDLE_TIMEOUT="${2:-120}"  # 2 minutes default

# Get absolute path to project directory
PROJECT_DIR="$(realpath "$PROJECT_DIR")"
echo "Monitoring Docker Compose logs in: $PROJECT_DIR"
echo "Idle timeout: $IDLE_TIMEOUT seconds"

# Check if docker compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Error: docker compose is not available"
    exit 1
fi

# Use docker compose (v2) if available, fall back to docker-compose (v1)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Error: Neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

# Check if we're in a directory with docker-compose.yaml
if [ ! -f "$PROJECT_DIR/docker-compose.yaml" ] && [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "Error: No docker-compose.yaml or docker-compose.yml found in $PROJECT_DIR"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Create temporary file for timestamp
TIMESTAMP_FILE=$(mktemp)
LAST_ACTIVITY=$(date +%s)
echo "$LAST_ACTIVITY" > "$TIMESTAMP_FILE"

# Function to clean up on exit
cleanup() {
    echo "Cleaning up..."
    # Kill background processes
    kill "$DOCKER_PID" 2>/dev/null || true
    kill "$MONITOR_PID" 2>/dev/null || true
    # Remove temp files
    rm -f "$TIMESTAMP_FILE"
    rm -f "$LOG_PIPE" 2>/dev/null || true
}
trap cleanup EXIT

# Function to send Telegram notification
send_notification() {
    local message="🕐 Docker Compose logs have been idle for ${IDLE_TIMEOUT} seconds in $(basename "$PROJECT_DIR")"
    echo "$message"

    # Call Telegram hook with JSON input
    local hook_input=$(jq -n \
        --arg cwd "$PROJECT_DIR" \
        --arg message "$message" \
        '{cwd: $cwd, message: $message}')

    # Call the Telegram hook (if available)
    if [ -f ~/.claude/hooks/tg.sh ]; then
        echo "$hook_input" | ~/.claude/hooks/tg.sh "docker_idle" &
    else
        echo "Warning: ~/.claude/hooks/tg.sh not found"
    fi
}

# Background monitor function
monitor_idle() {
    local notification_sent=false
    while true; do
        sleep 1
        local last_activity
        last_activity=$(cat "$TIMESTAMP_FILE")
        local current_time
        current_time=$(date +%s)
        local idle_time=$((current_time - last_activity))

        if [ $idle_time -ge $IDLE_TIMEOUT ] && [ "$notification_sent" = false ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Logs idle for $idle_time seconds"
            send_notification
            notification_sent=true
        elif [ $idle_time -lt $IDLE_TIMEOUT ] && [ "$notification_sent" = true ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log activity resumed"
            notification_sent=false
        fi
    done
}

# Start monitor in background
monitor_idle &
MONITOR_PID=$!

echo "Starting docker compose logs..."
echo "Monitoring started (PID: $$). Press Ctrl+C to stop."
echo "Last activity: $(date)"

# Create a named pipe for docker compose logs
LOG_PIPE=$(mktemp -u)
mkfifo "$LOG_PIPE"

# Start docker compose logs in background, writing to pipe
$DOCKER_COMPOSE logs -f --tail=0 > "$LOG_PIPE" 2>&1 &
DOCKER_PID=$!

# Read from pipe and update timestamp on each line
while IFS= read -r line; do
    # Update timestamp
    date +%s > "$TIMESTAMP_FILE"
    # Optionally display the line (comment out to reduce noise)
    # echo "[$(date '+%H:%M:%S')] $line"
done < "$LOG_PIPE"

# Clean up pipe (should not reach here until docker compose exits)
rm -f "$LOG_PIPE"
echo "docker compose logs command exited"