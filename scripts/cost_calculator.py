#!/usr/bin/env python3
"""
Cost Calculator - Calculate token costs and savings from context optimization.

Based on real pricing:
- Input tokens: ~$0.003/1K (Claude 3 Sonnet)
- Output tokens: ~$0.015/1K (Claude 3 Sonnet)

Tracks:
- Per-session costs
- Daily/monthly/yearly projections
- Savings from optimization
- ROI calculations
"""

import json
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelPricing:
    """Pricing per 1K tokens for a model."""
    name: str
    input_cost: float   # $ per 1K input tokens
    output_cost: float  # $ per 1K output tokens


# Model pricing (as of 2024)
MODEL_PRICING = {
    "claude-3-opus": ModelPricing("Claude 3 Opus", 0.015, 0.075),
    "claude-3-sonnet": ModelPricing("Claude 3 Sonnet", 0.003, 0.015),
    "claude-3-haiku": ModelPricing("Claude 3 Haiku", 0.00025, 0.00125),
    "claude-3-5-sonnet": ModelPricing("Claude 3.5 Sonnet", 0.003, 0.015),
    "claude-sonnet-4": ModelPricing("Claude Sonnet 4", 0.003, 0.015),
    "claude-opus-4": ModelPricing("Claude Opus 4", 0.015, 0.075),
    "gpt-4-turbo": ModelPricing("GPT-4 Turbo", 0.01, 0.03),
    "gpt-4o": ModelPricing("GPT-4o", 0.005, 0.015),
    "gpt-3.5-turbo": ModelPricing("GPT-3.5 Turbo", 0.0005, 0.0015),
}


class CostCalculator:
    """Calculate costs and savings from context optimization."""
    
    def __init__(self, model: str = "claude-3-sonnet"):
        """
        Initialize calculator.
        
        Args:
            model: Model name for pricing
        """
        self.pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-3-sonnet"])
    
    def calculate_session_cost(
        self,
        input_tokens: int,
        output_tokens: int = 500
    ) -> dict:
        """
        Calculate cost for a single session.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens (estimated)
            
        Returns:
            Cost breakdown
        """
        input_cost = (input_tokens / 1000) * self.pricing.input_cost
        output_cost = (output_tokens / 1000) * self.pricing.output_cost
        total_cost = input_cost + output_cost
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
            "model": self.pricing.name
        }
    
    def calculate_savings(
        self,
        original_tokens: int,
        optimized_tokens: int,
        sessions_per_day: int = 20,
        team_size: int = 1,
        output_tokens: int = 500
    ) -> dict:
        """
        Calculate savings from context optimization.
        
        Args:
            original_tokens: Original context tokens
            optimized_tokens: Optimized context tokens
            sessions_per_day: Average sessions per developer per day
            team_size: Number of developers
            output_tokens: Average output tokens per session
            
        Returns:
            Comprehensive savings breakdown
        """
        tokens_saved = original_tokens - optimized_tokens
        reduction_pct = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0
        
        # Per session costs
        original_session = self.calculate_session_cost(original_tokens, output_tokens)
        optimized_session = self.calculate_session_cost(optimized_tokens, output_tokens)
        savings_per_session = original_session["total_cost"] - optimized_session["total_cost"]
        
        # Daily calculations
        daily_sessions = sessions_per_day * team_size
        daily_original_cost = original_session["total_cost"] * daily_sessions
        daily_optimized_cost = optimized_session["total_cost"] * daily_sessions
        daily_savings = savings_per_session * daily_sessions
        
        # Monthly (22 working days)
        working_days = 22
        monthly_sessions = daily_sessions * working_days
        monthly_savings = daily_savings * working_days
        
        # Yearly (260 working days)
        yearly_working_days = 260
        yearly_sessions = daily_sessions * yearly_working_days
        yearly_savings = daily_savings * yearly_working_days
        
        return {
            "token_reduction": {
                "original": original_tokens,
                "optimized": optimized_tokens,
                "saved": tokens_saved,
                "reduction_percentage": round(reduction_pct, 1)
            },
            "per_session": {
                "original_cost": round(original_session["total_cost"], 4),
                "optimized_cost": round(optimized_session["total_cost"], 4),
                "savings": round(savings_per_session, 4)
            },
            "daily": {
                "sessions": daily_sessions,
                "original_cost": round(daily_original_cost, 2),
                "optimized_cost": round(daily_optimized_cost, 2),
                "savings": round(daily_savings, 2)
            },
            "monthly": {
                "sessions": monthly_sessions,
                "original_cost": round(daily_original_cost * working_days, 2),
                "optimized_cost": round(daily_optimized_cost * working_days, 2),
                "savings": round(monthly_savings, 2)
            },
            "yearly": {
                "sessions": yearly_sessions,
                "original_cost": round(daily_original_cost * yearly_working_days, 2),
                "optimized_cost": round(daily_optimized_cost * yearly_working_days, 2),
                "savings": round(yearly_savings, 2)
            },
            "context": {
                "sessions_per_day": sessions_per_day,
                "team_size": team_size,
                "model": self.pricing.name
            }
        }
    
    def calculate_relevance_waste(
        self,
        total_tokens: int,
        relevant_tokens: int,
        sessions_per_day: int = 20,
        team_size: int = 1
    ) -> dict:
        """
        Calculate waste from irrelevant context.
        
        Based on article: "70% of context is irrelevant to your current task"
        
        Args:
            total_tokens: Total context tokens loaded
            relevant_tokens: Actually relevant tokens
            sessions_per_day: Sessions per developer per day
            team_size: Number of developers
            
        Returns:
            Waste analysis
        """
        irrelevant_tokens = total_tokens - relevant_tokens
        relevance_pct = (relevant_tokens / total_tokens * 100) if total_tokens > 0 else 0
        waste_pct = 100 - relevance_pct
        
        # Cost of irrelevant tokens
        waste_cost_per_session = (irrelevant_tokens / 1000) * self.pricing.input_cost
        
        daily_sessions = sessions_per_day * team_size
        daily_waste = waste_cost_per_session * daily_sessions
        monthly_waste = daily_waste * 22
        yearly_waste = daily_waste * 260
        
        return {
            "relevance": {
                "total_tokens": total_tokens,
                "relevant_tokens": relevant_tokens,
                "irrelevant_tokens": irrelevant_tokens,
                "relevance_percentage": round(relevance_pct, 1),
                "waste_percentage": round(waste_pct, 1)
            },
            "wasted_cost": {
                "per_session": round(waste_cost_per_session, 4),
                "daily": round(daily_waste, 2),
                "monthly": round(monthly_waste, 2),
                "yearly": round(yearly_waste, 2)
            },
            "recommendation": self._get_waste_recommendation(waste_pct)
        }
    
    def _get_waste_recommendation(self, waste_pct: float) -> str:
        """Get recommendation based on waste percentage."""
        if waste_pct > 70:
            return "CRITICAL: Over 70% context waste. Implement tiered architecture immediately."
        elif waste_pct > 50:
            return "HIGH: Over 50% context waste. Review CLAUDE.md and move details to Tier 2 docs."
        elif waste_pct > 30:
            return "MODERATE: Over 30% waste. Optimize first 200 lines of CLAUDE.md."
        elif waste_pct > 10:
            return "LOW: Under 30% waste. Context is reasonably optimized."
        else:
            return "EXCELLENT: Under 10% waste. Context is well optimized."
    
    def generate_report(
        self,
        original_tokens: int,
        optimized_tokens: int,
        relevant_tokens: Optional[int] = None,
        sessions_per_day: int = 20,
        team_size: int = 5
    ) -> dict:
        """
        Generate comprehensive cost/savings report.
        
        Args:
            original_tokens: Original context tokens
            optimized_tokens: Optimized context tokens
            relevant_tokens: Actually relevant tokens (for waste analysis)
            sessions_per_day: Sessions per developer per day
            team_size: Number of developers
            
        Returns:
            Full report
        """
        savings = self.calculate_savings(
            original_tokens, optimized_tokens,
            sessions_per_day, team_size
        )
        
        report = {
            "summary": {
                "token_reduction": f"{savings['token_reduction']['reduction_percentage']}%",
                "monthly_savings": f"${savings['monthly']['savings']:.2f}",
                "yearly_savings": f"${savings['yearly']['savings']:.2f}",
                "team_size": team_size,
                "model": self.pricing.name
            },
            "detailed_savings": savings
        }
        
        if relevant_tokens is not None:
            waste = self.calculate_relevance_waste(
                original_tokens, relevant_tokens,
                sessions_per_day, team_size
            )
            report["relevance_analysis"] = waste
        
        # Add recommendations
        report["recommendations"] = self._generate_recommendations(savings, relevant_tokens)
        
        return report
    
    def _generate_recommendations(
        self,
        savings: dict,
        relevant_tokens: Optional[int]
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        reduction = savings["token_reduction"]["reduction_percentage"]
        
        if reduction < 30:
            recommendations.append(
                "🎯 Target 60% reduction by implementing tiered context architecture"
            )
        
        if savings["token_reduction"]["optimized"] > 800:
            recommendations.append(
                f"📝 Tier 1 context ({savings['token_reduction']['optimized']} tokens) exceeds "
                f"target of 800. Move detailed docs to Tier 2."
            )
        
        if savings["monthly"]["savings"] > 50:
            recommendations.append(
                f"💰 Significant savings potential: ${savings['yearly']['savings']:.0f}/year. "
                f"Prioritize optimization."
            )
        
        recommendations.append(
            "🚀 Implement session-start hooks to show status and save ~300 tokens/session"
        )
        
        recommendations.append(
            "📋 Create QUICK_REF.md for common commands (~200 tokens saved per lookup)"
        )
        
        return recommendations


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Calculate context optimization costs")
    parser.add_argument("--original", "-o", type=int, required=True, help="Original tokens")
    parser.add_argument("--optimized", "-p", type=int, required=True, help="Optimized tokens")
    parser.add_argument("--relevant", "-r", type=int, help="Relevant tokens (for waste analysis)")
    parser.add_argument("--sessions", "-s", type=int, default=20, help="Sessions per day per dev")
    parser.add_argument("--team", "-t", type=int, default=5, help="Team size")
    parser.add_argument("--model", "-m", default="claude-3-sonnet", help="Model for pricing")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    calc = CostCalculator(args.model)
    report = calc.generate_report(
        args.original,
        args.optimized,
        args.relevant,
        args.sessions,
        args.team
    )
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        # Pretty print
        print("\n" + "="*50)
        print("💰 CONTEXT OPTIMIZATION COST ANALYSIS")
        print("="*50)
        
        print(f"\n📊 Summary:")
        print(f"   Token Reduction: {report['summary']['token_reduction']}")
        print(f"   Monthly Savings: {report['summary']['monthly_savings']}")
        print(f"   Yearly Savings:  {report['summary']['yearly_savings']}")
        print(f"   Team Size:       {report['summary']['team_size']} developers")
        print(f"   Model:           {report['summary']['model']}")
        
        s = report['detailed_savings']
        print(f"\n📈 Detailed Breakdown:")
        print(f"   Per Session:  ${s['per_session']['original_cost']:.4f} → ${s['per_session']['optimized_cost']:.4f} (saves ${s['per_session']['savings']:.4f})")
        print(f"   Daily:        ${s['daily']['original_cost']:.2f} → ${s['daily']['optimized_cost']:.2f} (saves ${s['daily']['savings']:.2f})")
        print(f"   Monthly:      ${s['monthly']['original_cost']:.2f} → ${s['monthly']['optimized_cost']:.2f} (saves ${s['monthly']['savings']:.2f})")
        print(f"   Yearly:       ${s['yearly']['original_cost']:.2f} → ${s['yearly']['optimized_cost']:.2f} (saves ${s['yearly']['savings']:.2f})")
        
        if 'relevance_analysis' in report:
            r = report['relevance_analysis']
            print(f"\n🎯 Relevance Analysis:")
            print(f"   Relevant: {r['relevance']['relevance_percentage']}%")
            print(f"   Wasted:   {r['relevance']['waste_percentage']}%")
            print(f"   {r['recommendation']}")
        
        print(f"\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"   {rec}")
        
        print("\n" + "="*50)


if __name__ == "__main__":
    main()
