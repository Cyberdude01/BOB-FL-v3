#!/usr/bin/env python3
"""
Enhanced Monitoring Dashboard
Display real-time monitoring statistics and opportunities
"""

import sqlite3
import json
import sys
from datetime import datetime, timedelta
import pandas as pd

def create_dashboard():
    conn = sqlite3.connect('enhanced_flash_loan_research.db')
    
    # Get basic statistics
    cursor = conn.cursor()
    
    # Total opportunities
    cursor.execute("SELECT COUNT(*) FROM opportunities WHERE timestamp >= datetime('now', '-24 hours')")
    recent_opportunities = cursor.fetchone()[0]
    
    # Total profit estimate
    cursor.execute("SELECT SUM(estimated_profit_usd) FROM opportunities WHERE timestamp >= datetime('now', '-24 hours')")
    total_profit = cursor.fetchone()[0] or 0
    
    # Opportunities by network
    cursor.execute('''
        SELECT network, COUNT(*) as count, SUM(estimated_profit_usd) as profit
        FROM opportunities 
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY network
        ORDER BY count DESC
    ''')
    network_stats = cursor.fetchall()
    
    # Top opportunities
    cursor.execute('''
        SELECT network, protocol, token_pair, estimated_profit_usd, confidence_score
        FROM opportunities 
        WHERE timestamp >= datetime('now', '-24 hours')
        ORDER BY estimated_profit_usd DESC
        LIMIT 10
    ''')
    top_opportunities = cursor.fetchall()
    
    # Recent activity
    cursor.execute('''
        SELECT timestamp, network, protocol, opportunity_type, estimated_profit_usd
        FROM opportunities 
        WHERE timestamp >= datetime('now', '-1 hour')
        ORDER BY timestamp DESC
    ''')
    recent_activity = cursor.fetchall()
    
    conn.close()
    
    # Generate dashboard
    dashboard = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "recent_opportunities": recent_opportunities,
            "total_profit_24h": total_profit,
            "average_profit": total_profit / recent_opportunities if recent_opportunities > 0 else 0
        },
        "network_statistics": network_stats,
        "top_opportunities": top_opportunities,
        "recent_activity": recent_activity
    }
    
    return dashboard

if __name__ == "__main__":
    dashboard = create_dashboard()
    print(json.dumps(dashboard, indent=2))
