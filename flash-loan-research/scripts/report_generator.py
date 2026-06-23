#!/usr/bin/env python3
"""
Daily Report Generator for Flash Loan Opportunities
Generates comprehensive daily reports of found opportunities
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from monitor import FlashLoanMonitor, Opportunity

class ReportGenerator:
    """Generates daily reports for flash loan opportunities"""
    
    def __init__(self, monitor: FlashLoanMonitor):
        self.monitor = monitor
        self.logger = logging.getLogger(__name__)
        
    def generate_daily_report(self, date: datetime = None) -> str:
        """Generate daily report for specified date"""
        if date is None:
            date = datetime.now()
        
        # Get opportunities from the past 24 hours
        start_date = date - timedelta(days=1)
        opportunities = self._get_opportunities_by_date(start_date, date)
        
        # Generate report
        report = {
            "report_date": date.isoformat(),
            "period": f"{start_date.strftime('%Y-%m-%d %H:%M')} to {date.strftime('%Y-%m-%d %H:%M')}",
            "total_opportunities": len(opportunities),
            "total_estimated_profit": sum(opp.estimated_profit_usd for opp in opportunities),
            "opportunities_by_chain": self._group_by_chain(opportunities),
            "opportunities_by_type": self._group_by_type(opportunities),
            "top_opportunities": self._get_top_opportunities(opportunities),
            "market_summary": self._get_market_summary(),
            "recommendations": self._generate_recommendations(opportunities)
        }
        
        return json.dumps(report, indent=2)
    
    def _get_opportunities_by_date(self, start_date: datetime, end_date: datetime) -> List[Opportunity]:
        """Get opportunities within date range"""
        opportunities = []
        try:
            with open("logs/opportunities.log", "r") as f:
                for line in f:
                    try:
                        # Parse log line (simplified)
                        parts = line.strip().split(": ")
                        if len(parts) >= 2:
                            timestamp_str = parts[0]
                            opportunity_data = parts[1]
                            
                            # Parse timestamp
                            timestamp = datetime.fromisoformat(timestamp_str)
                            
                            if start_date <= timestamp <= end_date:
                                # Parse opportunity data (simplified)
                                opp = Opportunity(
                                    protocol="unknown",
                                    chain="unknown",
                                    opportunity_type="unknown",
                                    estimated_profit_usd=0,
                                    estimated_profit_percentage=0,
                                    required_gas_usd=0,
                                    timestamp=timestamp,
                                    details={"raw_data": opportunity_data}
                                )
                                opportunities.append(opp)
                    except Exception as e:
                        self.logger.warning(f"Error parsing log line: {e}")
                        continue
                        
        except FileNotFoundError:
            self.logger.info("No opportunities log file found")
        
        return opportunities
    
    def _group_by_chain(self, opportunities: List[Opportunity]) -> Dict[str, int]:
        """Group opportunities by blockchain"""
        chains = {}
        for opp in opportunities:
            chain = opp.chain
            chains[chain] = chains.get(chain, 0) + 1
        return chains
    
    def _group_by_type(self, opportunities: List[Opportunity]) -> Dict[str, int]:
        """Group opportunities by type"""
        types = {}
        for opp in opportunities:
            opp_type = opp.opportunity_type
            types[opp_type] = types.get(opp_type, 0) + 1
        return types
    
    def _get_top_opportunities(self, opportunities: List[Opportunity], limit: int = 5) -> List[Dict]:
        """Get top opportunities by profit"""
        sorted_opps = sorted(opportunities, key=lambda x: x.estimated_profit_usd, reverse=True)
        return [
            {
                "protocol": opp.protocol,
                "chain": opp.chain,
                "type": opp.opportunity_type,
                "profit_usd": opp.estimated_profit_usd,
                "profit_percentage": opp.estimated_profit_percentage,
                "timestamp": opp.timestamp.isoformat()
            }
            for opp in sorted_opps[:limit]
        ]
    
    def _get_market_summary(self) -> Dict:
        """Generate market summary"""
        return {
            "total_protocols_monitored": len(self.monitor.config.get("flash_loan_providers", {})),
            "total_dex_protocols": len(self.monitor.config.get("dex_protocols", {})),
            "chains_monitored": ["ethereum", "polygon", "avalanche", "bsc"],
            "monitoring_status": "active"
        }
    
    def _generate_recommendations(self, opportunities: List[Opportunity]) -> List[str]:
        """Generate recommendations based on opportunities"""
        recommendations = []
        
        if not opportunities:
            recommendations.append("No significant opportunities found today. Consider adjusting monitoring parameters.")
        else:
            # Analyze opportunity patterns
            avg_profit = sum(opp.estimated_profit_usd for opp in opportunities) / len(opportunities) if opportunities else 0
            
            if avg_profit > 1000:
                recommendations.append("High-value opportunities detected. Consider increasing monitoring frequency.")
            
            # Check for protocol-specific patterns
            chains = self._group_by_chain(opportunities)
            best_chain = max(chains.items(), key=lambda x: x[1]) if chains else None
            
            if best_chain and best_chain[1] > 0:
                recommendations.append(f"Most opportunities found on {best_chain[0]} - consider focusing analysis on this chain.")
        
        recommendations.append("Continue monitoring for emerging opportunities in stablecoin pools.")
        recommendations.append("Consider implementing automated execution for verified opportunities.")
        
        return recommendations
    
    def save_report(self, report: str, date: datetime = None):
        """Save report to file"""
        if date is None:
            date = datetime.now()
        
        filename = f"data/reports/{date.strftime('%Y-%m-%d')}_flash_loan_report.json"
        
        try:
            with open(filename, "w") as f:
                f.write(report)
            self.logger.info(f"Report saved to {filename}")
        except Exception as e:
            self.logger.error(f"Error saving report: {e}")
    
    def send_telegram_report(self, report: str, chat_id: str):
        """Send report via Telegram"""
        try:
            import requests
            
            # This would need actual Telegram bot setup
            telegram_url = f"https://api.telegram.org/botYOUR_TOKEN/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": f"Flash Loan Research Report\n\n{report}",
                "parse_mode": "HTML"
            }
            
            response = requests.post(telegram_url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info("Report sent via Telegram")
            
        except Exception as e:
            self.logger.error(f"Error sending Telegram report: {e}")

def main():
    """Main entry point for report generation"""
    import argparse
    from monitor import FlashLoanMonitor
    
    parser = argparse.ArgumentParser(description="Generate daily flash loan opportunity reports")
    parser.add_argument("--date", help="Date for report (YYYY-MM-DD)")
    parser.add_argument("--send-telegram", help="Send report via Telegram")
    
    args = parser.parse_args()
    
    # Initialize monitor and report generator
    monitor = FlashLoanMonitor()
    generator = ReportGenerator(monitor)
    
    # Parse date
    report_date = None
    if args.date:
        try:
            report_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            return
    
    # Generate report
    report = generator.generate_daily_report(report_date)
    
    # Save report
    generator.save_report(report, report_date)
    
    # Send via Telegram if requested
    if args.send_telegram:
        generator.send_telegram_report(report, args.send_telegram)
    
    print("Report generated successfully!")
    print(report)

if __name__ == "__main__":
    main()