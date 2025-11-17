#!/bin/bash
#
# VÉLØ Oracle - Cron Schedule Setup
#
# Installs cron jobs for self-learning loop
#
# Usage: ./scripts/cron_schedule.sh install
#        ./scripts/cron_schedule.sh remove
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

install_cron() {
    echo "Installing VÉLØ Oracle cron jobs..."
    
    # Create cron entries
    CRON_ENTRIES="
# VÉLØ Oracle - Self-Learning Loop
# Runs nightly at 2 AM
0 2 * * * cd $PROJECT_DIR && python3 scripts/self_learning_loop.py >> /var/log/velo/learning_loop.log 2>&1

# VÉLØ Oracle - Performance Report
# Runs weekly on Monday at 9 AM
0 9 * * 1 cd $PROJECT_DIR && python3 scripts/self_learning_loop.py --memory-dir /var/velo/memory >> /var/log/velo/weekly_report.log 2>&1
"
    
    # Add to crontab
    (crontab -l 2>/dev/null || echo ""; echo "$CRON_ENTRIES") | crontab -
    
    echo "✓ Cron jobs installed"
    echo ""
    echo "Scheduled jobs:"
    echo "  - Nightly learning loop: 2:00 AM daily"
    echo "  - Weekly performance report: 9:00 AM Monday"
    echo ""
    echo "Logs:"
    echo "  - Learning loop: /var/log/velo/learning_loop.log"
    echo "  - Weekly report: /var/log/velo/weekly_report.log"
}

remove_cron() {
    echo "Removing VÉLØ Oracle cron jobs..."
    
    # Remove VÉLØ entries from crontab
    crontab -l 2>/dev/null | grep -v "VÉLØ Oracle" | crontab - || true
    
    echo "✓ Cron jobs removed"
}

show_status() {
    echo "VÉLØ Oracle - Cron Status"
    echo "=========================="
    echo ""
    
    if crontab -l 2>/dev/null | grep -q "VÉLØ Oracle"; then
        echo "Status: ACTIVE"
        echo ""
        echo "Current jobs:"
        crontab -l 2>/dev/null | grep -A 1 "VÉLØ Oracle"
    else
        echo "Status: NOT INSTALLED"
        echo ""
        echo "Run './scripts/cron_schedule.sh install' to activate"
    fi
}

case "${1:-}" in
    install)
        install_cron
        ;;
    remove)
        remove_cron
        ;;
    status)
        show_status
        ;;
    *)
        echo "VÉLØ Oracle - Cron Schedule Manager"
        echo ""
        echo "Usage:"
        echo "  $0 install    Install cron jobs"
        echo "  $0 remove     Remove cron jobs"
        echo "  $0 status     Show cron status"
        exit 1
        ;;
esac

