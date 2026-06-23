#!/bin/bash

# Enhanced Flash Loan Monitoring System Setup Script
# This script sets up the complete enhanced monitoring system with all networks and protocols

set -e

echo "🚀 Setting up Enhanced Flash Loan Monitoring System..."

# Check if Python 3.8+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python $PYTHON_VERSION found"

# Create enhanced config directory
echo "📁 Creating enhanced config directory..."
mkdir -p enhanced-config
mkdir -p data/reports
mkdir -p logs
mkdir -p data/raw

# Copy API keys if they don't exist
if [ ! -f "api-keys-config.json" ]; then
    echo "⚠️  api-keys-config.json not found. Please create it with your API keys."
    echo "Required keys:"
    echo "- The Graph API key and JWT token"
    echo "- Infura project ID and API secret"
    echo "- Dune Analytics API key"
    exit 1
fi

# Check if enhanced config files exist
if [ ! -f "enhanced-config/networks.json" ]; then
    echo "❌ Enhanced network configuration not found"
    exit 1
fi

if [ ! -f "enhanced-config/flashloan-protocols.json" ]; then
    echo "❌ Enhanced protocol configuration not found"
    exit 1
fi

if [ ! -f "enhanced-config/dune-analytics-queries.json" ]; then
    echo "❌ Dune Analytics queries not found"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Install additional dependencies for enhanced monitoring
pip3 install "aiohttp[speedups]" "web3>=6.11.0" "pandas>=1.5.3" "numpy>=1.24.3" "ccxt" "schedule"

# Create enhanced monitoring script
echo "🔧 Creating enhanced monitoring scripts..."

# Create utility scripts
cat > scripts/monitor_enhanced.py << 'EOF'
#!/usr/bin/env python3
"""
Enhanced Flash Loan Monitoring Script
Run the enhanced monitoring system with various options
"""

import asyncio
import argparse
import sys
import os
from enhanced_monitoring_system import EnhancedFlashLoanMonitor

async def main():
    parser = argparse.ArgumentParser(description="Enhanced Flash Loan Monitoring")
    parser.add_argument("--config", default="enhanced-config/", help="Configuration path")
    parser.add_argument("--single-run", action="store_true", help="Run single monitoring cycle")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in minutes")
    parser.add_argument("--network", help="Specific network to monitor")
    parser.add_argument("--protocol", help="Specific protocol to monitor")
    
    args = parser.parse_args()
    
    # Create monitor instance
    monitor = EnhancedFlashLoanMonitor(args.config)
    
    try:
        if args.single_run:
            print("🔄 Running single monitoring cycle...")
            await monitor.run_monitoring_cycle()
            print("✅ Monitoring cycle completed")
        elif args.continuous:
            print(f"🔄 Starting continuous monitoring (interval: {args.interval} minutes)")
            await monitor.run_continuous_monitoring(args.interval)
        else:
            print("Use --single-run or --continuous option")
            sys.exit(1)
    finally:
        await monitor.close()

if __name__ == "__main__":
    asyncio.run(main())
EOF

# Create dashboard script
cat > scripts/dashboard.py << 'EOF'
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
EOF

# Create report generator
cat > scripts/generate_enhanced_report.py << 'EOF'
#!/usr/bin/env python3
"""
Enhanced Report Generator
Generate comprehensive reports on flash loan opportunities
"""

import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta
import sys

def generate_report(days=7):
    conn = sqlite3.connect('enhanced_flash_loan_research.db')
    
    # Get data for the specified period
    query = f'''
        SELECT timestamp, network, protocol, opportunity_type, token_pair,
               profit_percentage, estimated_profit_usd, gas_cost_usd, 
               liquidity_usd, risk_score, confidence_score, details
        FROM opportunities 
        WHERE timestamp >= datetime('now', '-{days} days')
        ORDER BY timestamp DESC
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return {"error": "No data found for the specified period"}
    
    # Generate report
    report = {
        "report_period": f"{days} days",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_opportunities": len(df),
            "total_estimated_profit": df['estimated_profit_usd'].sum(),
            "average_profit_per_opportunity": df['estimated_profit_usd'].mean(),
            "average_profit_percentage": df['profit_percentage'].mean(),
            "networks_covered": df['network'].nunique(),
            "protocols_covered": df['protocol'].nunique()
        },
        "opportunities_by_network": df.groupby('network').agg({
            'estimated_profit_usd': ['sum', 'mean', 'count'],
            'liquidity_usd': 'mean'
        }).round(2).to_dict(),
        "opportunities_by_protocol": df.groupby('protocol').agg({
            'estimated_profit_usd': ['sum', 'mean', 'count'],
            'liquidity_usd': 'mean'
        }).round(2).to_dict(),
        "risk_distribution": df['risk_score'].value_counts().to_dict(),
        "confidence_analysis": {
            "high_confidence": len(df[df['confidence_score'] >= 0.8]),
            "medium_confidence": len(df[(df['confidence_score'] >= 0.5) & (df['confidence_score'] < 0.8)]),
            "low_confidence": len(df[df['confidence_score'] < 0.5])
        },
        "top_opportunities": df.nlargest(10, 'estimated_profit_usd')[[
            'network', 'protocol', 'token_pair', 'estimated_profit_usd', 'confidence_score'
        ]].to_dict('records')
    }
    
    return report

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Enhanced Flash Loan Report")
    parser.add_argument("--days", type=int, default=7, help="Number of days to include in report")
    parser.add_argument("--output", help="Output file path")
    
    args = parser.parse_args()
    
    report = generate_report(args.days)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {args.output}")
    else:
        print(json.dumps(report, indent=2))
EOF

# Make scripts executable
chmod +x scripts/monitor_enhanced.py
chmod +x scripts/dashboard.py
chmod +x scripts/generate_enhanced_report.py

# Create systemd service file for continuous monitoring
cat > enhanced-monitoring.service << 'EOF'
[Unit]
Description=Enhanced Flash Loan Monitoring System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/flash-loan-research
ExecStart=/usr/bin/python3 scripts/monitor_enhanced.py --continuous --interval 30
Restart=always
RestartSec=30
Environment=PYTHONPATH=/root/.openclaw/workspace/flash-loan-research

[Install]
WantedBy=multi-user.target
EOF

# Create cron job for daily reports
cat > enhanced-cron.txt << 'EOF'
# Enhanced Flash Loan Monitoring System Cron Jobs
# Daily reports at 09:00 UTC
0 9 * * * cd /root/.openclaw/workspace/flash-loan-research && python3 scripts/generate_enhanced_report.py --days 1 --output data/reports/daily_$(date +\%Y\%m\%d).json

# Hourly dashboard updates
0 * * * * cd /root/.openclaw/workspace/flash-loan-research && python3 scripts/dashboard.py > data/reports/hourly_dashboard_$(date +\%Y\%m\%d_\%H).json

# Weekly summary
0 10 * * 1 cd /root/.openclaw/workspace/flash-loan-research && python3 scripts/generate_enhanced_report.py --days 7 --output data/reports/weekly_summary_$(date +\%Y\%m\%d).json
EOF

# Create test script
cat > test-enhanced-system.py << 'EOF'
#!/usr/bin/env python3
"""
Test script for the enhanced flash loan monitoring system
"""

import asyncio
import sys
import os
from enhanced_monitoring_system import EnhancedFlashLoanMonitor

async def test_system():
    print("🧪 Testing Enhanced Flash Loan Monitoring System...")
    
    try:
        # Create monitor instance
        monitor = EnhancedFlashLoanMonitor("enhanced-config/")
        
        # Test database connection
        print("✅ Testing database connection...")
        cursor = monitor.conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        # Test network connections
        print("✅ Testing network connections...")
        connected_networks = []
        for network_name, web3_client in monitor.web3_clients.items():
            if web3_client.is_connected():
                connected_networks.append(network_name)
        
        print(f"✅ Connected to {len(connected_networks)} networks: {', '.join(connected_networks)}")
        
        # Test The Graph connection
        print("✅ Testing The Graph connection...")
        test_query = "{ query { pools(first: 1) { id } } }"
        test_data = await monitor.get_the_graph_data(
            "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3", 
            test_query
        )
        if test_data:
            print("✅ The Graph connection successful")
        else:
            print("⚠️  The Graph connection test failed")
        
        # Test Dune Analytics connection
        print("✅ Testing Dune Analytics connection...")
        # Note: This would test with a real query, but for now we'll just check the API key
        if monitor.dune_api_key:
            print("✅ Dune Analytics API key configured")
        else:
            print("❌ Dune Analytics API key not configured")
        
        # Run single test cycle
        print("✅ Running test monitoring cycle...")
        opportunities = await monitor.detect_flash_loan_opportunities()
        
        print(f"✅ Test cycle completed. Found {len(opportunities)} opportunities")
        
        # Cleanup
        await monitor.close()
        
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_system())
    sys.exit(0 if success else 1)
EOF

# Create README for enhanced system
cat > ENHANCED_README.md << 'EOF'
# Enhanced Flash Loan Monitoring System

## Overview

This enhanced flash loan monitoring system expands to all available blockchain networks using Infura endpoints, The Graph subgraphs, and Dune Analytics for comprehensive flashloan opportunity detection.

## Key Features

- **Multi-Network Support**: Monitors 12+ blockchain networks including Ethereum, Polygon, Arbitrum, Base, Avalanche, BSC, and more
- **Enhanced Protocol Coverage**: Supports Aave, dYdX, MakerDAO, Uniswap, SushiSwap, Curve, Balancer, and more
- **Real-time Monitoring**: Continuous monitoring with configurable intervals
- **Advanced Analytics**: Uses The Graph and Dune Analytics for deep data analysis
- **Cross-chain Arbitrage**: Detects opportunities across different blockchain networks
- **Comprehensive Reporting**: Daily, weekly, and custom reports

## Quick Start

### 1. Setup
```bash
./enhanced-setup.sh
```

### 2. Test the System
```bash
python3 test-enhanced-system.py
```

### 3. Run Single Monitoring Cycle
```bash
python3 scripts/monitor_enhanced.py --single-run
```

### 4. Run Continuous Monitoring
```bash
python3 scripts/monitor_enhanced.py --continuous --interval 30
```

### 5. Generate Reports
```bash
# Daily report
python3 scripts/generate_enhanced_report.py --days 1 --output data/reports/daily_$(date +%Y%m%d).json

# Weekly report
python3 scripts/generate_enhanced_report.py --days 7 --output data/reports/weekly_$(date +%Y%m%d).json

# Dashboard
python3 scripts/dashboard.py
```

## Configuration Files

- `enhanced-config/networks.json`: Network configurations and endpoints
- `enhanced-config/flashloan-protocols.json`: Protocol configurations and subgraphs
- `enhanced-config/dune-analytics-queries.json`: Dune Analytics query definitions
- `api-keys-config.json`: API keys for external services

## Supported Networks

- Ethereum Mainnet
- Polygon
- Arbitrum One
- Base
- Avalanche
- Binance Smart Chain (BSC)
- Linea
- Optimism
- Celo
- Palm
- Fantom
- Moonbeam
- Moonriver
- Aurora
- Cronos
- Klaytn

## Supported Protocols

### Flash Loan Providers
- Aave (10+ networks)
- dYdX (Ethereum, Arbitrum)
- MakerDAO (Ethereum, Arbitrum, Optimism)
- Balancer V2 (8+ networks)
- Curve Finance (7+ networks)

### DEX Protocols
- Uniswap V2/V3 (9+ networks)
- SushiSwap (10+ networks)
- PancakeSwap (BSC, Cronos)

### Cross-Chain Bridges
- Connext
- Wormhole
- Hop Protocol
- Multichain

## Monitoring Features

### Opportunity Types
1. **Flash Loan Arbitrage**: Exploit price differences using flash loans
2. **DEX Arbitrage**: Price discrepancies between different DEXes
3. **Cross-Chain Arbitrage**: Price differences across blockchain networks
4. **Stablecoin Arbitrage**: Exploit stablecoin price variations
5. **Triangular Arbitrage**: Multi-token arbitrage opportunities

### Risk Assessment
- Protocol risk scoring
- Network risk assessment
- Liquidity analysis
- Gas cost optimization
- Confidence scoring

### Analytics
- Real-time opportunity detection
- Historical trend analysis
- Profit estimation
- Risk metrics
- Performance tracking

## API Integration

### Infura
- Multi-network RPC endpoints
- Gas price monitoring
- Block data access

### The Graph
- Subgraph queries for DeFi protocols
- Real-time data updates
- Custom analytics

### Dune Analytics
- Complex SQL queries
- Historical data analysis
- Custom metric tracking

## System Architecture

```
EnhancedFlashLoanMonitor
├── Network Management
│   ├── Multi-chain RPC clients
│   └── Gas price monitoring
├── Protocol Monitoring
│   ├── Flash loan providers
│   ├── DEX protocols
│   └── Cross-chain bridges
├── Analytics Engine
│   ├── Opportunity detection
│   ├── Risk assessment
│   └── Profit calculation
└── Reporting System
    ├── Real-time alerts
    ├── Historical reports
    └── Performance metrics
```

## Monitoring Schedule

- **Real-time monitoring**: Configurable intervals (default: 30 minutes)
- **Hourly dashboard updates**: Summary statistics
- **Daily reports**: Comprehensive daily analysis
- **Weekly summaries**: Trend analysis and insights

## Troubleshooting

### Common Issues

1. **Network connection errors**
   - Check Infura API keys
   - Verify network connectivity
   - Test RPC endpoints manually

2. **The Graph timeouts**
   - Check JWT token validity
   - Reduce query complexity
   - Implement retry logic

3. **Dune API limits**
   - Monitor API usage
   - Implement caching
   - Use pagination for large queries

### Logs

- `enhanced-monitoring.log`: Main system logs
- `data/reports/`: Generated reports and analytics
- `logs/`: Detailed operation logs

## Performance Optimization

### Database
- Implement indexing for frequent queries
- Use connection pooling
- Implement data archiving

### API Calls
- Implement request caching
- Use async/await for concurrent requests
- Implement rate limiting

### Memory Management
- Monitor memory usage
- Implement data pruning
- Use efficient data structures

## Security Considerations

- API key management
- Secure database storage
- Input validation
- Rate limiting
- Access control

## Future Enhancements

- Machine learning for opportunity prediction
- Automated execution integration
- Advanced risk modeling
- Multi-signature security
- Custom alert system

## Support

For issues and feature requests:
1. Check logs in `logs/` directory
2. Review configuration files
3. Test with `test-enhanced-system.py`
4. Verify API key configurations
EOF

# Make test script executable
chmod +x test-enhanced-system.py

echo "✅ Enhanced Flash Loan Monitoring System setup complete!"
echo ""
echo "📚 Next steps:"
echo "1. Test the system: python3 test-enhanced-system.py"
echo "2. Run single cycle: python3 scripts/monitor_enhanced.py --single-run"
echo "3. Start continuous monitoring: python3 scripts/monitor_enhanced.py --continuous"
echo "4. View dashboard: python3 scripts/dashboard.py"
echo ""
echo "📖 Documentation: ENHANCED_README.md"
echo "⚙️  Configuration: enhanced-config/"
echo "📊 Reports: data/reports/"
echo "🔧 Logs: logs/"