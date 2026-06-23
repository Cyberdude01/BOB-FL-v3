#!/usr/bin/env python3
"""
Daily Flash Loan Research Report Generator
Generates comprehensive daily reports of identified opportunities
"""

import sqlite3
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

class DailyReportGenerator:
    def __init__(self, config_path="research-config.json"):
        self.config = self.load_config(config_path)
        self.conn = sqlite3.connect('flash_loan_research.db')
        self.setup_email()
    
    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def setup_email(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.smtp_username = "your_email@gmail.com"
        self.smtp_password = "your_app_password"
    
    def get_daily_opportunities(self, date):
        """Get opportunities for specific date"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM opportunities 
            WHERE DATE(timestamp) = DATE(?)
            ORDER BY profit_percentage DESC
        ''', (date,))
        
        columns = [desc[0] for desc in cursor.description]
        opportunities = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return opportunities
    
    def get_trend_analysis(self, days=5):
        """Analyze trends over past days"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as opportunity_count,
                AVG(profit_percentage) as avg_profit,
                MAX(profit_percentage) as max_profit,
                MIN(risk_score) as best_risk_score
            FROM opportunities
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        '''.format(days))
        
        return cursor.fetchall()
    
    def generate_report(self, date):
        """Generate daily research report"""
        opportunities = self.get_daily_opportunities(date)
        trends = self.get_trend_analysis()
        
        report = {
            'date': date,
            'summary': {
                'total_opportunities': len(opportunities),
                'high_value_opportunities': len([o for o in opportunities if o['profit_percentage'] > 0.01]),
                'low_risk_opportunities': len([o for o in opportunities if o['risk_score'] < 50]),
                'total_potential_profit': sum(o['estimated_profit_usd'] for o in opportunities)
            },
            'opportunities': opportunities,
            'trends': trends,
            'recommendations': self.generate_recommendations(opportunities, trends)
        }
        
        return report
    
    def generate_recommendations(self, opportunities, trends):
        """Generate strategic recommendations"""
        recommendations = []
        
        if len(opportunities) == 0:
            recommendations.append("No significant opportunities found today. Monitor for volatility.")
        else:
            # High profit opportunities
            high_profit = [o for o in opportunities if o['profit_percentage'] > 0.01]
            if high_profit:
                recommendations.append(f"Found {len(high_profit)} high-profit opportunities (>1%). Top: {high_profit[0]['pair']} with {high_profit[0]['profit_percentage']*100:.2f}% profit.")
            
            # Low risk opportunities
            low_risk = [o for o in opportunities if o['risk_score'] < 30]
            if low_risk:
                recommendations.append(f"Found {len(low_risk)} low-risk opportunities (risk score < 30). Consider these for safer arbitrage.")
        
        # Trend analysis
        if trends:
            recent_trend = trends[-1]
            previous_trend = trends[-2] if len(trends) > 1 else None
            
            if previous_trend:
                change = recent_trend['opportunity_count'] - previous_trend['opportunity_count']
                if change > 0:
                    recommendations.append(f"Opportunity count increased by {change} from previous day.")
                elif change < 0:
                    recommendations.append(f"Opportunity count decreased by {abs(change)} from previous day.")
        
        return recommendations
    
    def create_visualizations(self, report):
        """Create charts for the report"""
        # Opportunity count by type
        opportunity_types = {}
        for opp in report['opportunities']:
            opp_type = opp['opportunity_type']
            opportunity_types[opp_type] = opportunity_types.get(opp_type, 0) + 1
        
        plt.figure(figsize=(10, 6))
        plt.bar(opportunity_types.keys(), opportunity_types.values())
        plt.title(f'Flash Loan Opportunities by Type - {report["date"]}')
        plt.xlabel('Opportunity Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('opportunity_types.png')
        plt.close()
        
        # Profit distribution
        profits = [opp['profit_percentage'] * 100 for opp in report['opportunities']]
        plt.figure(figsize=(10, 6))
        plt.hist(profits, bins=20, alpha=0.7, color='blue')
        plt.title(f'Profit Distribution - {report["date"]}')
        plt.xlabel('Profit Percentage (%)')
        plt.ylabel('Frequency')
        plt.axvline(x=0.5, color='red', linestyle='--', label='0.5% threshold')
        plt.legend()
        plt.tight_layout()
        plt.savefig('profit_distribution.png')
        plt.close()
    
    def send_report_email(self, report):
        """Send report via email"""
        if not self.config['alerting']['email']:
            return
        
        msg = MimeMultipart()
        msg['From'] = self.smtp_username
        msg['To'] = self.config['alerting']['email']
        msg['Subject'] = f"Flash Loan Research Report - {report['date']}"
        
        # Create email body
        email_body = f"""
# Flash Loan Research Report
**Date**: {report['date']}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total Opportunities: {report['summary']['total_opportunities']}
- High Value (>1%): {report['summary']['high_value_opportunities']}
- Low Risk (<50): {report['summary']['low_risk_opportunities']}
- Total Potential Profit: ${report['summary']['total_potential_profit']:,.2f}

## Top Opportunities
"""
        
        for i, opp in enumerate(report['opportunities'][:5], 1):
            email_body += f"""
{i}. **{opp['pair']}** ({opp['protocol']})
   - Type: {opp['opportunity_type']}
   - Profit: {opp['profit_percentage']*100:.2f}%
   - Estimated Profit: ${opp['estimated_profit_usd']:,.2f}
   - Risk Score: {opp['risk_score']}/100
"""
        
        email_body += f"""
## Recommendations
"""
        for rec in report['recommendations']:
            email_body += f"- {rec}\n"
        
        msg.attach(MimeText(email_body, 'html'))
        
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()
            print("Report sent successfully!")
        except Exception as e:
            print(f"Error sending email: {e}")
    
    def generate_and_send_report(self, date):
        """Main method to generate and send report"""
        print(f"Generating report for {date}...")
        report = self.generate_report(date)
        
        # Save report as JSON
        with open(f'report_{date}.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Create visualizations
        if report['opportunities']:
            self.create_visualizations(report)
        
        # Send email report
        self.send_report_email(report)
        
        print(f"Report generated and sent for {date}")
        return report

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python daily-report-generator.py <date>")
        sys.exit(1)
    
    date = sys.argv[1]
    generator = DailyReportGenerator()
    generator.generate_and_send_report(date)