#!/bin/bash

# Flash Loan Research System Setup Script
# This script sets up the entire flash loan monitoring system

set -e

echo "🚀 Setting up Flash Loan Research System..."

# Configuration variables
PROJECT_ROOT="/root/.openclaw/workspace/flash-loan-research"
PYTHON_VERSION="3.8"
LOG_DIR="$PROJECT_ROOT/logs"
DATA_DIR="$PROJECT_ROOT/data"
REPORTS_DIR="$PROJECT_ROOT/data/reports"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    log_error "This script should not be run as root"
    exit 1
fi

# Create directory structure
log "Creating directory structure..."
mkdir -p "$LOG_DIR"
mkdir -p "$DATA_DIR/raw"
mkdir -p "$DATA_DIR/processed"
mkdir -p "$DATA_DIR/reports"
mkdir -p "$SCRIPTS_DIR"

# Set permissions
chmod +x "$PROJECT_ROOT/scripts/"*.py
chmod +x "$PROJECT_ROOT/setup.sh"

# Check Python version
log "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log "Python version: $PYTHON_VERSION"

# Install Python dependencies
log "Installing Python dependencies..."
cd "$PROJECT_ROOT"
if python3 -m pip install -r requirements.txt; then
    log "Dependencies installed successfully"
else
    log_error "Failed to install dependencies"
    exit 1
fi

# Create virtual environment (optional)
log "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies in virtual environment
pip install -r requirements.txt

# Check if required tools are installed
log "Checking required tools..."
tools=("curl" "jq" "crontab")
for tool in "${tools[@]}"; do
    if ! command -v "$tool" &> /dev/null; then
        log_error "$tool is not installed"
        exit 1
    fi
done

# Create API keys template
log "Creating API keys template..."
cat > "$PROJECT_ROOT/config/api_keys_template.json" << EOF
{
  "defillama": {
    "api_key": "YOUR_DEFI_LLAMA_API_KEY"
  },
  "dune_analytics": {
    "api_key": "YOUR_DUNE_ANALYTICS_API_KEY"
  },
  "etherscan": {
    "api_key": "YOUR_ETHERSCAN_API_KEY"
  },
  "polygon_scan": {
    "api_key": "YOUR_POLYGON_SCAN_API_KEY"
  },
  "avalanche_scan": {
    "api_key": "YOUR_AVALANCHE_SCAN_API_KEY"
  },
  "bscan": {
    "api_key": "YOUR_BSC_SCAN_API_KEY"
  }
}
EOF

log "API keys template created at $PROJECT_ROOT/config/api_keys_template.json"
log_warn "Please copy api_keys_template.json to api_keys.json and add your API keys"

# Set up log rotation
log "Setting up log rotation..."
cat > /tmp/logrotate.conf << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF

sudo mv /tmp/logrotate.conf /etc/logrotate.d/flash-loan-research

# Create environment file
log "Creating environment file..."
cat > "$PROJECT_ROOT/.env" << EOF
# Flash Loan Research System Environment Variables
PROJECT_ROOT=$PROJECT_ROOT
PYTHON_PATH=$PROJECT_ROOT/venv/bin/python
LOG_LEVEL=INFO
MONITORING_INTERVAL=30
REPORT_TIME=09:00 UTC
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_TELEGRAM_CHAT_ID
EOF

# Make setup script executable
chmod +x "$PROJECT_ROOT/setup.sh"

# Initialize git repository (optional)
if command -v git &> /dev/null; then
    log "Initializing git repository..."
    cd "$PROJECT_ROOT"
    if [ ! -d ".git" ]; then
        git init
        git add .
        git commit -m "Initial commit: Flash Loan Research System"
    fi
fi

log "✅ Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Copy config/api_keys_template.json to config/api_keys.json"
echo "2. Add your API keys to the config file"
echo "3. Review and adjust config/protocols.json and config/alert_thresholds.json"
echo "4. Run setup_cron.py to set up automated monitoring:"
echo "   python scripts/setup_cron.py --setup"
echo "5. Start monitoring:"
echo "   python scripts/monitor.py --continuous"
echo "6. Generate daily reports:"
echo "   python scripts/report_generator.py"
echo ""
echo "📊 System will run for 5 days and generate daily reports"
echo "🔄 Monitoring runs every 30 minutes"
echo "📈 Daily reports generated at 09:00 UTC"
echo ""