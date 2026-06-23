#!/usr/bin/env python3
"""
Weekly Summary Generator for Flash Loan Research
Compiles weekly reports and insights
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from monitor import Opportunity

class WeeklySummaryGenerator:
    """Generates weekly summaries of flash loan opportunities"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_weekly_summary(self, end_date: datetime = None) -> str:
        """Generate comprehensive weekly summary"""
        if end_date is None:
            end_date = datetime.now()
        
        start_date = end_date - timedelta(days=7)
        
        # Collect data for the week
        weekly_data = self._collect_weekly_data(start_date, end_date)
        
        # Generate summary report
        summary = {
            "summary_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "generated_at": end_date.isoformat(),
            "total_opportunities": weekly_data["total_opportunities"],
            "total_profit_estimate": weekly_data["total_profit_estimate"],
            "average_profit_per_opportunity": weekly_data["average_profit_per_opportunity"],
            "best_day": weekly_data["best_day"],
            "best_chain": weekly_data["best_chain"],
            "best_protocol": weekly_data["best_protocol"],
            "opportunity_trends": self._analyze_trends(weekly_data),
            "market_conditions": self._analyze_market_conditions(weekly_data),
            "recommendations": self._generate_weekly_recommendations(weekly_data),
            "weekly_breakdown": self._generate_daily_breakdown(weekly_data)
        }
        
        return json.dumps(summary, indent=2)
    
    def _collect_weekly_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """Collect opportunity data for the week"""
        daily_data = []
        total_opportunities = 0
        total_profit = 0
        daily_breakdown = {}
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            opportunities = self._get_opportunities_for_date(date_str)
            
            day_profit = sum(opp.estimated_profit_usd for opp in opportunities)
            daily_breakdown[date_str] = {
                "opportunities": len(opportunities),
                "total_profit": day_profit,
                "average_profit": day_profit / len(opportunities) if opportunities else 0
            }
            
            total_opportunities += len(opportunities)
            total_profit += day_profit
            daily_data.extend(opportunities)
            
            current_date += timedelta(days=1)
        
        # Find best performing day
        best_day = max(daily_breakdown.items(), key=lambda x: x[1]["total_profit"]) if daily_breakdown else None
        
        # Analyze by chain and protocol
        chain_performance = self._analyze_by_chain(daily_data)
        protocol_performance = self._analyze_by_protocol(daily_data)
        
        return {
            "total_opportunities": total_opportunities,
            "total_profit_estimate": total_profit,
            "average_profit_per_opportunity": total_profit / total_opportunities if total_opportunities > 0 else 0,
            "best_day": best_day[0] if best_day else None,
            "best_chain": max(chain_performance.items(), key=lambda x: x[1]["total_profit"])[0] if chain_performance else None,
            "best_protocol": max(protocol_performance.items(), key=lambda x: x[1]["total_profit"])[0] if protocol_performance else None,
            "daily_data": daily_data,
            "chain_performance": chain_performance,
            "protocol_performance": protocol_performance,
            "daily_breakdown": daily_breakdown
        }
    
    def _get_opportunities_for_date(self, date_str: str) -> List[Opportunity]:
        """Get opportunities for a specific date"""
        opportunities = []
        try:
            with open("logs/opportunities.log", "r") as f:
                for line in f:
                    try:
                        parts = line.strip().split(": ")
                        if len(parts) >= 2:
                            timestamp_str = parts[0]
                            opportunity_data = parts[1]
                            
                            # Extract date part
                            date_part = timestamp_str.split('T')[0]
                            if date_part == date_str:
                                # Parse opportunity data (simplified)
                                opp = Opportunity(
                                    protocol="unknown",
                                    chain="unknown",
                                    opportunity_type="unknown",
                                    estimated_profit_usd=0,
                                    estimated_profit_percentage=0,
                                    required_gas_usd=0,
                                    timestamp=datetime.fromisoformat(timestamp_str),
                                    details={"raw_data": opportunity_data}
                                )
                                opportunities.append(opp)
                    except Exception as e:
                        self.logger.warning(f"Error parsing log line: {e}")
                        continue
                        
        except FileNotFoundError:
            self.logger.info(f"No opportunities log file found for {date_str}")
        
        return opportunities
    
    def _analyze_by_chain(self, opportunities: List[Opportunity]) -> Dict:
        """Analyze performance by blockchain"""
        chain_data = {}
        
        for opp in opportunities:
            chain = opp.chain
            if chain not in chain_data:
                chain_data[chain] = {
                    "opportunities": 0,
                    "total_profit": 0,
                    "average_profit": 0
                }
            
            chain_data[chain]["opportunities"] += 1
            chain_data[chain]["total_profit"] += opp.estimated_profit_usd
        
        # Calculate averages
        for chain in chain_data:
            count = chain_data[chain]["opportunities"]
            chain_data[chain]["average_profit"] = chain_data[chain]["total_profit"] / count if count > 0 else 0
        
        return chain_data
    
    def _analyze_by_protocol(self, opportunities: List[Opportunity]) -> Dict:
        """Analyze performance by protocol"""
        protocol_data = {}
        
        for opp in opportunities:
            protocol = opp.protocol
            if protocol not in protocol_data:
                protocol_data[protocol] = {
                    "opportunities": 0,
                    "total_profit": 0,
                    "average_profit": 0
                }
            
            protocol_data[protocol]["opportunities"] += 1
            protocol_data[protocol]["total_profit"] += opp.estimated_profit_usd
        
        # Calculate averages
        for protocol in protocol_data:
            count = protocol_data[protocol]["opportunities"]
            protocol_data[protocol]["average_profit"] = protocol_data[protocol]["total_profit"] / count if count > 0 else 0
        
        return protocol_data
    
    def _analyze_trends(self, weekly_data: Dict) -> Dict:
        """Analyze trends in opportunity data"""
        trends = {
            "opportunity_frequency_trend": "stable",
            "profit_trend": "stable",
            "volatility_level": "medium"
        }
        
        # Analyze daily opportunity counts for trend
        daily_counts = [data["opportunities"] for data in weekly_data["daily_breakdown"].values()]
        
        if len(daily_counts) > 1:
            first_half = daily_counts[:len(daily_counts)//2]
            second_half = daily_counts[len(daily_counts)//2:]
            
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            if avg_second > avg_first * 1.2:
                trends["opportunity_frequency_trend"] = "increasing"
            elif avg_second < avg_first * 0.8:
                trends["opportunity_frequency_trend"] = "decreasing"
        
        # Analyze profit trends
        daily_profits = [data["total_profit"] for data in weekly_data["daily_breakdown"].values()]
        
        if len(daily_profits) > 1:
            profit_variance = sum((p - sum(daily_profits)/len(daily_profits))**2 for p in daily_profits) / len(daily_profits)
            std_dev = profit_variance ** 0.5
            
            if std_dev > sum(daily_profits) / len(daily_profits) * 0.5:
                trends["volatility_level"] = "high"
            elif std_dev < sum(daily_profits) / len(daily_profits) * 0.2:
                trends["volatility_level"] = "low"
        
        return trends
    
    def _analyze_market_conditions(self, weekly_data: Dict) -> Dict:
        """Analyze market conditions"""
        return {
            "market_liquidity": "adequate",
            "volatility_level": "medium",
            "competition_level": "moderate",
            "recommended_strategy": "patient monitoring"
        }
    
    def _generate_weekly_recommendations(self, weekly_data: Dict) -> List[str]:
        """Generate weekly recommendations"""
        recommendations = []
        
        if weekly_data["total_opportunities"] == 0:
            recommendations.append("No opportunities found this week. Consider expanding monitoring scope or adjusting parameters.")
        elif weekly_data["total_profit_estimate"] > 10000:
            recommendations.append("High-value opportunities detected. Consider implementing automated execution.")
        
        # Check chain performance
        if weekly_data["best_chain"]:
            recommendations.append(f"Focus on {weekly_data['best_chain']} chain where most opportunities were found.")
        
        # Check protocol performance
        if weekly_data["best_protocol"]:
            recommendations.append(f"Prioritize {weekly_data['best_protocol']} protocol for monitoring.")
        
        # General recommendations
        recommendations.append("Continue monitoring stablecoin pools for arbitrage opportunities.")
        recommendations.append("Consider monitoring cross-chain bridges for additional opportunities.")
        recommendations.append("Review and adjust opportunity thresholds based on market conditions.")
        
        return recommendations
    
    def _generate_daily_breakdown(self, weekly_data: Dict) -> List[Dict]:
        """Generate daily breakdown of opportunities"""
        breakdown = []
        
        for date_str, day_data in weekly_data["daily_breakdown"].items():
            breakdown.append({
                "date": date_str,
                "opportunities_count": day_data["opportunities"],
                "total_profit_usd": day_data["total_profit"],
                "average_profit_usd": day_data["average_profit"]
            })
        
        return breakdown

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate weekly flash loan research summary")
    parser.add_argument("--end-date", help="End date for summary (YYYY-MM-DD)")
    parser.add_argument("--save-report", action="store_true", help="Save report to file")
    
    args = args = parser.parse_args()
    
    # Parse end date
    end_date = None
    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            return
    
    # Generate summary
    generator = WeeklySummaryGenerator()
    summary = generator.generate_weekly_summary(end_date)
    
    # Save report if requested
    if args.save_report:
        filename = f"data/reports/weekly_summary_{end_date.strftime('%Y-%m-%d') if end_date else datetime.now().strftime('%Y-%m-%d')}.json"
        with open(filename, "w") as f:
            f.write(summary)
        print(f"Weekly summary saved to {filename}")
    
    # Print summary
    print("Weekly Summary:")
    print(summary)

if __name__ == "__main__":
    main()