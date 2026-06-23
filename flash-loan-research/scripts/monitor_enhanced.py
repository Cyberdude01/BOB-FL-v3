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
