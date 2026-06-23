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
