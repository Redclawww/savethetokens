#!/usr/bin/env python3
"""
Metrics Collector - Track and report context optimization metrics.

Implements measurement system from the article:
- Token usage tracking per session
- Hook execution time
- Context miss rate
- Cost savings tracking
- Trend analysis
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict, fields
from typing import Optional


@dataclass
class SessionMetrics:
    """Metrics for a single session."""
    session_id: str
    timestamp: str
    
    # Token metrics
    total_tokens: int
    tier1_tokens: int
    tier2_tokens: int
    tier3_tokens: int  # Should be 0 (linked only)
    
    # Relevance metrics
    high_relevance_tokens: int
    low_relevance_tokens: int
    
    # Performance metrics
    hook_execution_ms: float
    context_load_ms: float
    
    # Quality metrics
    context_miss_count: int  # Times Claude asked for more context
    quality_preserved: bool
    
    # Cost metrics
    estimated_cost_usd: float
    savings_vs_baseline_usd: float

    # Experiment metadata (optional)
    experiment_id: str = ""
    variant: str = "optimized"  # optimized | control
    assignment_key: str = ""
    intent: str = "generic"
    budget: int = 0

    # Section-wise token accounting
    baseline_tokens: int = 0
    post_filter_tokens: int = 0
    output_tokens: int = 0
    package_filter_tokens_saved: int = 0
    pruning_tokens_saved: int = 0
    overall_tokens_saved: int = 0
    package_filter_pct: float = 0.0
    pruning_pct: float = 0.0
    overall_pct: float = 0.0
    within_budget: bool = True


class MetricsCollector:
    """Collects and analyzes context optimization metrics."""
    
    # Targets from the article
    TARGETS = {
        "tier1_tokens_max": 800,
        "hook_execution_ms_max": 2000,
        "context_miss_rate_max": 0.10,
        "token_reduction_target": 0.60,
    }
    
    def __init__(self, metrics_dir: Optional[Path] = None):
        """
        Initialize metrics collector.
        
        Args:
            metrics_dir: Directory to store metrics files
        """
        if metrics_dir:
            self.metrics_dir = Path(metrics_dir)
        else:
            self.metrics_dir = Path.home() / ".claude" / "savethetokens" / "metrics"
        
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[dict] = None
        self._session_start: Optional[float] = None
    
    def start_session(self) -> str:
        """Start tracking a new session."""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self._session_start = time.time()
        self._current_session = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "events": [],
            "tokens": {},
            "timings": {},
            "quality": {"miss_count": 0, "preserved": True},
            "experiment": {
                "id": "",
                "variant": "optimized",
                "assignment_key": "",
            },
            "plan": {},
        }
        return session_id

    def set_experiment(
        self,
        experiment_id: Optional[str] = None,
        variant: str = "optimized",
        assignment_key: Optional[str] = None
    ):
        """Attach experiment metadata to the active session."""
        if not self._current_session:
            self.start_session()

        self._current_session["experiment"] = {
            "id": experiment_id or "",
            "variant": variant or "optimized",
            "assignment_key": assignment_key or "",
        }
    
    def record_event(self, event_type: str, data: dict):
        """Record an event in the current session."""
        if not self._current_session:
            self.start_session()
        
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": (time.time() - self._session_start) * 1000,
            **data
        }
        self._current_session["events"].append(event)
        
        # Update aggregated metrics
        if event_type == "tokens_loaded":
            self._current_session["tokens"] = {
                **self._current_session.get("tokens", {}),
                **data
            }
        elif event_type == "hook_executed":
            self._current_session["timings"]["hook_execution_ms"] = data.get("duration_ms", 0)
        elif event_type == "context_miss":
            self._current_session["quality"]["miss_count"] += 1
    
    def record_tokens(
        self,
        total: int,
        tier1: int = 0,
        tier2: int = 0,
        tier3: int = 0,
        high_relevance: int = 0,
        low_relevance: int = 0
    ):
        """Record token usage."""
        self.record_event("tokens_loaded", {
            "total": total,
            "tier1": tier1,
            "tier2": tier2,
            "tier3": tier3,
            "high_relevance": high_relevance,
            "low_relevance": low_relevance
        })
    
    def record_hook_timing(self, duration_ms: float):
        """Record hook execution time."""
        self.record_event("hook_executed", {"duration_ms": duration_ms})
    
    def record_context_miss(self, file_requested: str):
        """Record when Claude had to request additional context."""
        self.record_event("context_miss", {"file_requested": file_requested})

    def record_plan_metrics(
        self,
        *,
        intent: str,
        budget: int,
        baseline_tokens: int,
        post_filter_tokens: int,
        output_tokens: int,
        package_filter_tokens_saved: int,
        pruning_tokens_saved: int,
        overall_tokens_saved: int,
        package_filter_pct: float,
        pruning_pct: float,
        overall_pct: float,
        within_budget: bool
    ):
        """Record plan-level section metrics for later A/B analysis."""
        if not self._current_session:
            self.start_session()

        payload = {
            "intent": intent,
            "budget": budget,
            "baseline_tokens": baseline_tokens,
            "post_filter_tokens": post_filter_tokens,
            "output_tokens": output_tokens,
            "package_filter_tokens_saved": package_filter_tokens_saved,
            "pruning_tokens_saved": pruning_tokens_saved,
            "overall_tokens_saved": overall_tokens_saved,
            "package_filter_pct": float(package_filter_pct),
            "pruning_pct": float(pruning_pct),
            "overall_pct": float(overall_pct),
            "within_budget": bool(within_budget),
        }
        self._current_session["plan"] = payload
        self.record_event("plan_metrics", payload)
    
    def end_session(self, quality_preserved: bool = True) -> SessionMetrics:
        """End session and save metrics."""
        if not self._current_session:
            raise ValueError("No active session")
        
        # Calculate cost (Claude 3 Sonnet pricing)
        tokens = self._current_session.get("tokens", {})
        total_tokens = int(tokens.get("total", 0))
        plan_stats = self._current_session.get("plan", {})
        experiment = self._current_session.get("experiment", {})

        output_tokens = int(plan_stats.get("output_tokens", total_tokens))
        billable_tokens = output_tokens if output_tokens > 0 else total_tokens
        baseline_tokens = int(plan_stats.get("baseline_tokens", 0))
        if baseline_tokens <= 0:
            # Backward-compatible fallback for old sessions without explicit baseline.
            baseline_tokens = max(total_tokens, int(total_tokens * 2.5))

        cost_per_1k = 0.003
        estimated_cost = (billable_tokens / 1000) * cost_per_1k
        baseline_cost = (baseline_tokens / 1000) * cost_per_1k
        savings = baseline_cost - estimated_cost
        
        metrics = SessionMetrics(
            session_id=self._current_session["session_id"],
            timestamp=self._current_session["timestamp"],
            total_tokens=total_tokens,
            tier1_tokens=tokens.get("tier1", 0),
            tier2_tokens=tokens.get("tier2", 0),
            tier3_tokens=tokens.get("tier3", 0),
            high_relevance_tokens=tokens.get("high_relevance", 0),
            low_relevance_tokens=tokens.get("low_relevance", 0),
            hook_execution_ms=self._current_session.get("timings", {}).get("hook_execution_ms", 0),
            context_load_ms=(time.time() - self._session_start) * 1000,
            context_miss_count=self._current_session["quality"]["miss_count"],
            quality_preserved=quality_preserved,
            estimated_cost_usd=round(estimated_cost, 6),
            savings_vs_baseline_usd=round(savings, 6),
            experiment_id=experiment.get("id", ""),
            variant=experiment.get("variant", "optimized"),
            assignment_key=experiment.get("assignment_key", ""),
            intent=plan_stats.get("intent", "generic"),
            budget=int(plan_stats.get("budget", 0)),
            baseline_tokens=baseline_tokens,
            post_filter_tokens=int(plan_stats.get("post_filter_tokens", total_tokens)),
            output_tokens=output_tokens,
            package_filter_tokens_saved=int(plan_stats.get("package_filter_tokens_saved", 0)),
            pruning_tokens_saved=int(plan_stats.get("pruning_tokens_saved", 0)),
            overall_tokens_saved=int(plan_stats.get("overall_tokens_saved", 0)),
            package_filter_pct=round(float(plan_stats.get("package_filter_pct", 0.0)), 2),
            pruning_pct=round(float(plan_stats.get("pruning_pct", 0.0)), 2),
            overall_pct=round(float(plan_stats.get("overall_pct", 0.0)), 2),
            within_budget=bool(plan_stats.get("within_budget", True)),
        )
        
        # Save to file
        self._save_metrics(metrics)
        
        # Reset session
        self._current_session = None
        self._session_start = None
        
        return metrics
    
    def _save_metrics(self, metrics: SessionMetrics):
        """Save metrics to daily file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.metrics_dir / f"metrics_{date_str}.jsonl"
        
        with open(file_path, "a") as f:
            f.write(json.dumps(asdict(metrics)) + "\n")
    
    def load_metrics(self, days: int = 7) -> list[SessionMetrics]:
        """Load metrics from the last N days."""
        metrics = []
        metric_fields = {f.name for f in fields(SessionMetrics)}
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.metrics_dir / f"metrics_{date_str}.jsonl"
            
            if file_path.exists():
                with open(file_path) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            payload = {k: v for k, v in data.items() if k in metric_fields}
                            try:
                                metrics.append(SessionMetrics(**payload))
                            except TypeError:
                                # Ignore malformed lines while preserving older valid history.
                                continue
        
        return metrics
    
    def get_summary(self, days: int = 7) -> dict:
        """Get summary statistics for the last N days."""
        metrics = self.load_metrics(days)
        
        if not metrics:
            return {
                "period_days": days,
                "session_count": 0,
                "message": "No metrics recorded yet"
            }
        
        # Aggregate stats
        total_tokens = sum(m.total_tokens for m in metrics)
        total_cost = sum(m.estimated_cost_usd for m in metrics)
        total_savings = sum(m.savings_vs_baseline_usd for m in metrics)
        
        tier1_tokens = sum(m.tier1_tokens for m in metrics)
        hook_times = [m.hook_execution_ms for m in metrics if m.hook_execution_ms > 0]
        miss_counts = [m.context_miss_count for m in metrics]
        
        # Check targets
        avg_tier1 = tier1_tokens / len(metrics) if metrics else 0
        avg_hook_time = sum(hook_times) / len(hook_times) if hook_times else 0
        total_sessions = len(metrics)
        total_misses = sum(miss_counts)
        miss_rate = total_misses / total_sessions if total_sessions else 0
        
        target_status = {
            "tier1_tokens": {
                "target": f"<{self.TARGETS['tier1_tokens_max']}",
                "actual": round(avg_tier1),
                "met": avg_tier1 < self.TARGETS['tier1_tokens_max']
            },
            "hook_execution": {
                "target": f"<{self.TARGETS['hook_execution_ms_max']}ms",
                "actual": f"{round(avg_hook_time)}ms",
                "met": avg_hook_time < self.TARGETS['hook_execution_ms_max']
            },
            "context_miss_rate": {
                "target": f"<{self.TARGETS['context_miss_rate_max'] * 100}%",
                "actual": f"{round(miss_rate * 100, 1)}%",
                "met": miss_rate < self.TARGETS['context_miss_rate_max']
            }
        }
        
        return {
            "period_days": days,
            "session_count": len(metrics),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "total_savings_usd": round(total_savings, 4),
            "avg_tokens_per_session": round(total_tokens / len(metrics)),
            "avg_cost_per_session": round(total_cost / len(metrics), 6),
            "target_status": target_status,
            "quality_preserved_rate": f"{sum(1 for m in metrics if m.quality_preserved) / len(metrics) * 100:.0f}%"
        }
    
    def generate_report(self, days: int = 7) -> str:
        """Generate human-readable report."""
        summary = self.get_summary(days)
        
        if summary.get("session_count", 0) == 0:
            return "📊 No metrics recorded yet. Start tracking with `start_session()`."
        
        lines = [
            "=" * 60,
            "📊 CONTEXT GOVERNOR METRICS REPORT",
            "=" * 60,
            "",
            f"📅 Period: Last {summary['period_days']} days",
            f"🔢 Sessions: {summary['session_count']}",
            "",
            "💰 COST ANALYSIS",
            "-" * 30,
            f"  Total tokens: {summary['total_tokens']:,}",
            f"  Total cost: ${summary['total_cost_usd']:.4f}",
            f"  Total savings: ${summary['total_savings_usd']:.4f}",
            f"  Avg per session: ${summary['avg_cost_per_session']:.6f}",
            "",
            "🎯 TARGET STATUS",
            "-" * 30,
        ]
        
        for metric, status in summary.get("target_status", {}).items():
            icon = "✅" if status.get("met") else "❌"
            lines.append(f"  {icon} {metric}: {status['actual']} (target: {status['target']})")
        
        lines.extend([
            "",
            f"✨ Quality preserved: {summary.get('quality_preserved_rate', 'N/A')}",
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def get_trend(self, days: int = 30) -> dict:
        """Get trend data for visualization."""
        metrics = self.load_metrics(days)
        
        # Group by day
        daily = {}
        for m in metrics:
            date = m.timestamp[:10]  # YYYY-MM-DD
            if date not in daily:
                daily[date] = {
                    "sessions": 0,
                    "tokens": 0,
                    "cost": 0,
                    "savings": 0,
                    "misses": 0
                }
            daily[date]["sessions"] += 1
            daily[date]["tokens"] += m.total_tokens
            daily[date]["cost"] += m.estimated_cost_usd
            daily[date]["savings"] += m.savings_vs_baseline_usd
            daily[date]["misses"] += m.context_miss_count
        
        # Sort by date
        sorted_days = sorted(daily.items())
        
        return {
            "dates": [d[0] for d in sorted_days],
            "sessions": [d[1]["sessions"] for d in sorted_days],
            "tokens": [d[1]["tokens"] for d in sorted_days],
            "cost": [round(d[1]["cost"], 4) for d in sorted_days],
            "savings": [round(d[1]["savings"], 4) for d in sorted_days],
            "miss_rate": [
                round(d[1]["misses"] / d[1]["sessions"] * 100, 1) if d[1]["sessions"] > 0 else 0
                for d in sorted_days
            ]
        }


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Context optimization metrics")
    parser.add_argument("--report", "-r", action="store_true", help="Show metrics report")
    parser.add_argument("--summary", "-s", action="store_true", help="Show summary")
    parser.add_argument("--trend", "-t", action="store_true", help="Show trend data")
    parser.add_argument("--days", "-d", type=int, default=7, help="Days to analyze")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    
    args = parser.parse_args()
    
    collector = MetricsCollector()
    
    if args.report:
        print(collector.generate_report(args.days))
    
    elif args.summary:
        summary = collector.get_summary(args.days)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            for key, value in summary.items():
                if isinstance(value, dict):
                    print(f"{key}:")
                    for k, v in value.items():
                        print(f"  {k}: {v}")
                else:
                    print(f"{key}: {value}")
    
    elif args.trend:
        trend = collector.get_trend(args.days)
        if args.json:
            print(json.dumps(trend, indent=2))
        else:
            print("Trend data (use --json for structured output):")
            print(f"  Dates: {len(trend['dates'])} days of data")
            if trend['dates']:
                print(f"  Range: {trend['dates'][0]} to {trend['dates'][-1]}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
