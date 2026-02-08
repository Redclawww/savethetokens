#!/usr/bin/env python3
"""
Context Governor - Main Entry Point

Analyzes context and generates an optimized execution plan.
Automatically filters package directories (node_modules, __pycache__, etc.)

Features:
- Tiered context architecture (Tier 1/2/3)
- Relevance scoring based on current work
- Automatic package filtering
- Cost tracking and metrics
- Quality preservation guarantees

Usage:
    python govern.py --budget 8000 --output plan.json
    python govern.py --budget 4000 --intent debugging
    python govern.py --tiered --relevance
    python govern.py --help
"""

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Import local modules
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from analyze import ContextAnalyzer
from estimate_tokens import TokenEstimator
from classify_intent import IntentClassifier
from prune import ContextPruner
from select_model import ModelSelector
from path_filter import PathFilter
from tiered_context import TieredContextClassifier
from relevance_scorer import ContextRelevanceScorer
from metrics_collector import MetricsCollector


def create_execution_plan(
    context_units: list[dict],
    budget: int,
    intent: str | None = None,
    target_model: str = "claude-3-sonnet",
    query: str | None = None,
    prefer_cost_savings: bool = True,
    auto_filter_packages: bool = True,
    use_tiered_architecture: bool = True,
    use_relevance_scoring: bool = True,
    track_metrics: bool = True,
    project_root: str | None = None,
    metrics_dir: str | None = None,
    experiment_id: str | None = None,
    experiment_variant: str = "optimized",
    assignment_key: str | None = None,
    apply_pruning: bool = True,
) -> dict:
    """
    Generate an optimized execution plan.
    
    Args:
        context_units: List of context unit dicts
        budget: Token budget
        intent: Task intent (or None for auto-classification)
        target_model: Target model ID
        query: Optional query for relevance scoring
        prefer_cost_savings: Whether to optimize for cost
        auto_filter_packages: Whether to filter node_modules, __pycache__, etc.
        use_tiered_architecture: Apply tiered context (Tier 1/2/3)
        use_relevance_scoring: Score relevance based on work context
        track_metrics: Track metrics for cost analysis
        project_root: Project root for relevance detection
        metrics_dir: Optional metrics output directory
        experiment_id: Optional experiment identifier for telemetry
        experiment_variant: Experiment variant label ("control" or "optimized")
        assignment_key: Deterministic assignment key for experiment routing
        apply_pruning: Whether to apply pruning/summarization stage
        
    Returns:
        Execution plan dict
    """
    plan_id = str(uuid.uuid4())[:8]
    
    # Initialize components
    estimator = TokenEstimator()
    classifier = IntentClassifier()
    pruner = ContextPruner()
    model_selector = ModelSelector()
    path_filter = PathFilter() if auto_filter_packages else None
    tiered_classifier = TieredContextClassifier() if use_tiered_architecture else None
    relevance_scorer = ContextRelevanceScorer(project_root) if use_relevance_scoring else None
    metrics_collector = None
    metrics_setup_warning = None
    if track_metrics:
        try:
            metrics_collector = MetricsCollector(
                Path(metrics_dir) if metrics_dir else None
            )
        except OSError as exc:
            metrics_setup_warning = f"Metrics disabled: {exc}"
    
    # Start metrics tracking
    if metrics_collector:
        metrics_collector.start_session()
        metrics_collector.set_experiment(
            experiment_id=experiment_id,
            variant=experiment_variant,
            assignment_key=assignment_key
        )
    
    # Step 0: Estimate tokens for all units first so filtering savings are accurate.
    for unit in context_units:
        if "tokens" not in unit:
            unit["tokens"] = estimator.estimate(unit.get("content", ""))
    original_total_tokens = sum(u.get("tokens", 0) for u in context_units)

    # Step 1: Filter out package directories (node_modules, __pycache__, etc.)
    filtered_packages = []
    if path_filter:
        context_units, filtered_packages = path_filter.filter_context_units(context_units)

    # Calculate token savings from filtering.
    filtered_tokens = sum(u.get("tokens", 0) for u in filtered_packages)
    post_filter_tokens = sum(u.get("tokens", 0) for u in context_units)
    
    # Step 1.5: Apply relevance scoring (from work context)
    relevance_stats = None
    if relevance_scorer:
        work_context = relevance_scorer.get_work_context()
        for unit in context_units:
            if "file_path" in unit or "path" in unit:
                file_path = unit.get("file_path") or unit.get("path", "")
                score = relevance_scorer.score_file(file_path)
                unit["relevance"] = {
                    "score": score.score,
                    "category": score.category,
                    "reason": score.reason
                }
            elif "content" in unit:
                score = relevance_scorer.score_content(unit["content"])
                unit["relevance"] = {
                    "score": score.score,
                    "category": score.category,
                    "reason": score.reason
                }
        
        # Analyze relevance waste
        relevance_stats = relevance_scorer.analyze_context_waste(context_units)
    
    # Step 1.6: Apply tiered classification
    tiered_stats = None
    if tiered_classifier:
        classified = tiered_classifier.classify_units(context_units)
        tiers = classified.get("tiers", {})

        # Map classified units back to source units by id.
        unit_tier_map: dict[str, int] = {}
        for tier_name, tier_data in tiers.items():
            tier_num = 2
            if tier_name.startswith("tier_1"):
                tier_num = 1
            elif tier_name.startswith("tier_3"):
                tier_num = 3

            for tier_unit in tier_data.get("units", []):
                unit_id = tier_unit.get("id")
                if unit_id:
                    unit_tier_map[unit_id] = tier_num

        for unit in context_units:
            unit_id = unit.get("id")
            if unit_id in unit_tier_map:
                unit["tier"] = unit_tier_map[unit_id]

        optimization = classified.get("optimization", {})
        tiered_stats = {
            "enabled": True,
            "tier_1_tokens": tiers.get("tier_1_critical", {}).get("token_count", 0),
            "tier_2_tokens": tiers.get("tier_2_contextual", {}).get("token_count", 0),
            "tier_3_tokens": tiers.get("tier_3_reference", {}).get("token_count", 0),
            "current_startup_tokens": optimization.get("current_startup_tokens", 0),
            "optimized_startup_tokens": optimization.get("optimized_startup_tokens", 0),
            "tokens_saved_per_session": optimization.get("tokens_saved_per_session", 0),
            "reduction_percentage": optimization.get("reduction_percentage", 0),
            "recommendations": classified.get("recommendations", []),
        }
    
    # Collect post-filter statistics
    total_input_tokens = post_filter_tokens
    units_by_type = {}
    for unit in context_units:
        t = unit.get("type", "unknown")
        units_by_type[t] = units_by_type.get(t, 0) + 1
    message_count = units_by_type.get("message", 0) + units_by_type.get("instruction", 0)
    
    # Step 2: Classify intent if not provided
    if intent is None:
        all_content = " ".join(u.get("content", "") for u in context_units)
        intent_result = classifier.classify(all_content, query)
        classified_intent = intent_result["intent"]
        intent_confidence = intent_result["confidence"]
    else:
        classified_intent = intent
        intent_confidence = 1.0
    
    # Step 3: Get model recommendation
    model_rec = model_selector.select(
        target_model,
        classified_intent,
        total_input_tokens,
        prefer_cost_savings
    )
    
    # Step 4: Calculate budget allocation
    response_reserve = int(budget * 0.20)  # 20% for response
    system_reserve = 500  # Fixed system prompt budget
    context_budget = budget - response_reserve - system_reserve
    
    # Step 5: Prune/optimize context
    prune_budget = context_budget if apply_pruning else max(context_budget, total_input_tokens)
    prune_result = pruner.prune(
        context_units,
        prune_budget,
        classified_intent,
        query
    )
    if not apply_pruning:
        prune_result.setdefault("warnings", []).append(
            "Experiment control variant: pruning disabled to measure baseline behavior."
        )
    
    # Build optimized context array
    optimized_context = []
    for decision in prune_result["decisions"]:
        optimized_context.append({
            "id": decision["unit_id"],
            "type": decision.get("type", "unknown"),
            "action": decision["action"],
            "original_tokens": decision.get("original_tokens", 0),
            "tokens": decision.get("final_tokens", 0),
            "priority": decision.get("priority", 50),
            "reason": decision["reason"]
        })
    
    # Calculate statistics
    final_tokens = sum(d["tokens"] for d in optimized_context if d["action"] != "prune")
    pruning_tokens_saved = total_input_tokens - final_tokens
    overall_tokens_saved = original_total_tokens - final_tokens
    reduction_pct = (
        overall_tokens_saved / original_total_tokens * 100
        if original_total_tokens > 0 else 0
    )
    
    units_kept = sum(1 for d in optimized_context if d["action"] == "keep")
    units_summarized = sum(1 for d in optimized_context if d["action"] == "summarize")
    units_pruned = sum(1 for d in optimized_context if d["action"] == "prune")
    session_hygiene = _get_session_hygiene(
        message_count=message_count,
        input_tokens=total_input_tokens,
        optimized_tokens=final_tokens,
        context_budget=context_budget
    )
    
    # Build the execution plan
    plan = {
        "plan_id": plan_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        
        "input_summary": {
            "total_units": len(context_units),
            "total_tokens": total_input_tokens,
            "pre_filter_total_tokens": original_total_tokens,
            "units_by_type": units_by_type,
            "packages_filtered": {
                "count": len(filtered_packages),
                "tokens_saved": filtered_tokens,
                "reduction_percentage": round(
                    (filtered_tokens / original_total_tokens * 100)
                    if original_total_tokens > 0 else 0,
                    1,
                ),
                "examples": [p.get("path", p.get("id", "unknown")) for p in filtered_packages[:5]]
            } if filtered_packages else None
        },
        
        "constraints": {
            "token_budget": budget,
            "target_model": target_model,
            "intent": classified_intent
        },
        "experiment": {
            "enabled": bool(experiment_id),
            "id": experiment_id,
            "variant": experiment_variant,
            "assignment_key": assignment_key,
        },
        
        "recommendations": {
            "model": {
                "recommended": model_rec["recommended_model"],
                "original": model_rec.get("original_model"),
                "reason": model_rec["reason"],
                "cost_savings_estimate": model_rec.get("cost_savings_estimate"),
                "alternatives": model_rec.get("alternatives", [])
            },
            "budget_allocation": {
                "system_prompt": system_reserve,
                "context": context_budget,
                "response_reserve": response_reserve
            }
        },
        
        "optimized_context": optimized_context,
        
        "statistics": {
            "input_tokens": original_total_tokens,
            "post_filter_tokens": total_input_tokens,
            "output_tokens": final_tokens,
            "tokens_saved": overall_tokens_saved,
            "reduction_percentage": round(reduction_pct, 1),
            "units_kept": units_kept,
            "units_summarized": units_summarized,
            "units_pruned": units_pruned
        },

        "savings_breakdown": {
            "baseline_tokens": original_total_tokens,
            "after_filter_tokens": total_input_tokens,
            "after_pruning_tokens": final_tokens,
            "package_filtering": {
                "tokens_saved": filtered_tokens,
                "percentage_of_baseline": round(
                    (filtered_tokens / original_total_tokens * 100)
                    if original_total_tokens > 0 else 0,
                    1,
                ),
            },
            "pruning_and_summarization": {
                "tokens_saved": pruning_tokens_saved,
                "percentage_of_baseline": round(
                    (pruning_tokens_saved / original_total_tokens * 100)
                    if original_total_tokens > 0 else 0,
                    1,
                ),
                "percentage_of_post_filter": round(
                    (pruning_tokens_saved / total_input_tokens * 100)
                    if total_input_tokens > 0 else 0,
                    1,
                ),
            },
            "overall": {
                "tokens_saved": overall_tokens_saved,
                "percentage_of_baseline": round(reduction_pct, 1),
            },
            "tiered_startup": {
                "enabled": bool(tiered_stats),
                "current_tokens": tiered_stats.get("current_startup_tokens", 0) if tiered_stats else 0,
                "optimized_tokens": tiered_stats.get("optimized_startup_tokens", 0) if tiered_stats else 0,
                "tokens_saved": tiered_stats.get("tokens_saved_per_session", 0) if tiered_stats else 0,
                "reduction_percentage": tiered_stats.get("reduction_percentage", 0) if tiered_stats else 0,
            },
            "relevance_waste": {
                "enabled": bool(relevance_stats),
                "wasted_tokens": relevance_stats.get("wasted_tokens", 0) if relevance_stats else 0,
                "waste_percentage": relevance_stats.get("waste_percentage", 0) if relevance_stats else 0,
            },
        },
        
        "validation": {
            "total_tokens": final_tokens + system_reserve,
            "within_budget": (final_tokens + system_reserve) <= (budget - response_reserve),
            "budget_remaining": context_budget - final_tokens
        },
        
        "explainability": {
            "strategy_used": prune_result.get("strategy", "hybrid"),
            "intent_confidence": round(intent_confidence, 2),
            "pruning_threshold": prune_result.get("threshold", 0.3)
        },
        
        # TIERED ARCHITECTURE (from article)
        "tiered_architecture": tiered_stats if tiered_stats else {
            "enabled": False,
            "reason": "Disabled by configuration"
        },
        
        # RELEVANCE SCORING (from article)
        "relevance_analysis": relevance_stats if relevance_stats else {
            "enabled": False,
            "reason": "Disabled by configuration"
        },
        
        # QUALITY PRESERVATION - Most important section
        "quality_assurance": {
            "quality_impact": prune_result.get("quality_impact", "unknown"),
            "quality_preserved": prune_result.get("quality_preserved", True),
            "protected_types_kept": True,  # System prompts, recent messages always kept
            "fail_safe_defaults_applied": True,
            "recommendation": _get_quality_recommendation(
                prune_result.get("quality_impact", "none"),
                reduction_pct
            )
        },

        # SESSION HYGIENE - proactive compacting and safe resets
        "session_hygiene": session_hygiene,
        
        "warnings": prune_result.get("warnings", [])
    }

    if metrics_setup_warning:
        plan["warnings"].append(metrics_setup_warning)
    
    # End metrics tracking
    if metrics_collector:
        tier1_tokens = tiered_stats.get("tier_1_tokens", 0) if tiered_stats else 0
        tier2_tokens = tiered_stats.get("tier_2_tokens", 0) if tiered_stats else 0
        tier3_tokens = tiered_stats.get("tier_3_tokens", 0) if tiered_stats else 0
        high_rel = relevance_stats.get("by_category", {}).get("high", {}).get("tokens", 0) if relevance_stats else 0
        low_rel = relevance_stats.get("wasted_tokens", 0) if relevance_stats else 0
        
        metrics_collector.record_tokens(
            total=final_tokens,
            tier1=tier1_tokens,
            tier2=tier2_tokens,
            tier3=tier3_tokens,
            high_relevance=high_rel,
            low_relevance=low_rel
        )

        metrics_collector.record_plan_metrics(
            intent=classified_intent,
            budget=budget,
            baseline_tokens=original_total_tokens,
            post_filter_tokens=total_input_tokens,
            output_tokens=final_tokens,
            package_filter_tokens_saved=filtered_tokens,
            pruning_tokens_saved=pruning_tokens_saved,
            overall_tokens_saved=overall_tokens_saved,
            package_filter_pct=plan["savings_breakdown"]["package_filtering"]["percentage_of_baseline"],
            pruning_pct=plan["savings_breakdown"]["pruning_and_summarization"]["percentage_of_baseline"],
            overall_pct=plan["savings_breakdown"]["overall"]["percentage_of_baseline"],
            within_budget=plan["validation"]["within_budget"]
        )
        
        session_metrics = metrics_collector.end_session(
            quality_preserved=prune_result.get("quality_preserved", True)
        )
        
        # Add metrics to plan
        plan["metrics"] = {
            "session_id": session_metrics.session_id,
            "estimated_cost_usd": session_metrics.estimated_cost_usd,
            "savings_vs_baseline_usd": session_metrics.savings_vs_baseline_usd
        }
    
    return plan


def _get_quality_recommendation(quality_impact: str, reduction_pct: float) -> str:
    """Generate quality recommendation based on pruning impact."""
    if quality_impact == "none":
        return "Full context preserved - optimal output quality expected"
    elif quality_impact == "minimal":
        return "Minimal pruning applied - output quality should be unaffected"
    elif quality_impact == "low":
        return "Light pruning applied - output quality preserved"
    elif quality_impact == "moderate":
        return f"Moderate reduction ({reduction_pct:.0f}%) - review output for completeness"
    else:
        return (
            f"Significant reduction ({reduction_pct:.0f}%) - "
            "consider increasing budget for better output quality"
        )


def _resolve_experiment_variant(
    experiment_id: str | None,
    requested_variant: str,
    assignment_key: str | None
) -> str:
    """
    Resolve experiment variant for telemetry experiments.

    - If no experiment is active, always use optimized behavior.
    - If variant is explicitly provided, honor it.
    - For `auto`: deterministic split when assignment_key is provided,
      otherwise pseudo-random split per invocation.
    """
    if not experiment_id:
        return "optimized"
    if requested_variant in {"control", "optimized"}:
        return requested_variant

    seed_key = assignment_key
    if not seed_key:
        # Fallback random assignment when no stable key is provided.
        return "control" if int(uuid.uuid4().hex[:8], 16) % 2 == 0 else "optimized"

    digest = hashlib.sha256(f"{experiment_id}:{seed_key}".encode("utf-8")).hexdigest()
    return "control" if int(digest[:8], 16) % 2 == 0 else "optimized"


def _get_session_hygiene(
    message_count: int,
    input_tokens: int,
    optimized_tokens: int,
    context_budget: int
) -> dict:
    """Recommend proactive compact/reset actions from session pressure."""
    safe_budget = max(context_budget, 1)
    input_utilization = (input_tokens / safe_budget) * 100
    optimized_utilization = (optimized_tokens / safe_budget) * 100

    if input_utilization >= 80 or message_count >= 55:
        action = "checkpoint_then_compact_immediately"
        playbook = [
            "Create a short checkpoint file (goal, done, next, touched files)",
            "Run /compact now to reduce context pressure",
            "If switching to unrelated work, start a fresh session after compact",
        ]
    elif input_utilization >= 50 or message_count >= 35:
        action = "checkpoint_then_compact"
        playbook = [
            "Create a short checkpoint before ending this task chunk",
            "Run /compact around this point instead of waiting for hard limits",
        ]
    elif input_utilization >= 35 or message_count >= 25:
        action = "prepare_checkpoint"
        playbook = [
            "Prepare checkpoint bullets now to make next compact cheap",
            "Run /context periodically and compact around 50% usage",
        ]
    else:
        action = "continue"
        playbook = [
            "Continue in the same session for this task",
            "Keep one chat window per task to avoid context drift",
        ]

    return {
        "message_count_estimate": message_count,
        "input_context_utilization_pct": round(input_utilization, 1),
        "optimized_context_utilization_pct": round(optimized_utilization, 1),
        "recommended_action": action,
        "playbook": playbook,
        "token_hygiene_habits": [
            "Use ! <command> for direct terminal commands when no reasoning is needed",
            "Break large requests into smaller task chunks",
            "Run /context periodically and compact around 50% usage",
            "Save checkpoints before compact/clear to preserve continuity",
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Context Governor - Generate optimized execution plans"
    )
    parser.add_argument(
        "--budget", "-b",
        type=int,
        default=8000,
        help="Token budget (default: 8000)"
    )
    parser.add_argument(
        "--intent", "-i",
        choices=["code_generation", "debugging", "explanation", "search", "planning", "review", "generic"],
        help="Task intent (auto-detected if not specified)"
    )
    parser.add_argument(
        "--model", "-m",
        default="claude-3-sonnet",
        help="Target model (default: claude-3-sonnet)"
    )
    parser.add_argument(
        "--output", "-o",
        default="execution_plan.json",
        help="Output file (default: execution_plan.json)"
    )
    parser.add_argument(
        "--input", "-f",
        help="Input JSON file with context units"
    )
    parser.add_argument(
        "--query", "-q",
        help="Query string for relevance scoring"
    )
    parser.add_argument(
        "--no-cost-optimize",
        action="store_true",
        help="Disable cost optimization"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output except errors"
    )
    parser.add_argument(
        "--tiered",
        action="store_true",
        default=True,
        help="Enable tiered context architecture (default: enabled)"
    )
    parser.add_argument(
        "--no-tiered",
        action="store_true",
        help="Disable tiered context architecture"
    )
    parser.add_argument(
        "--relevance",
        action="store_true",
        default=True,
        help="Enable relevance scoring (default: enabled)"
    )
    parser.add_argument(
        "--no-relevance",
        action="store_true",
        help="Disable relevance scoring"
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        default=True,
        help="Track metrics (default: enabled)"
    )
    parser.add_argument(
        "--no-metrics",
        action="store_true",
        help="Disable metrics tracking"
    )
    parser.add_argument(
        "--project-root",
        help="Project root for relevance detection"
    )
    parser.add_argument(
        "--metrics-dir",
        help="Directory to store metrics (default: ~/.claude/savethetokens/metrics)"
    )
    parser.add_argument(
        "--experiment-id",
        help="Experiment ID for live telemetry (enables A/B metadata)"
    )
    parser.add_argument(
        "--variant",
        choices=["optimized", "control", "auto"],
        default="optimized",
        help="Experiment variant (default: optimized)"
    )
    parser.add_argument(
        "--assignment-key",
        help="Stable key for deterministic auto variant assignment (e.g. ticket ID)"
    )
    
    args = parser.parse_args()
    
    # Load context units
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
            if isinstance(data, dict):
                context_units = data.get("context_units", data)
            elif isinstance(data, list):
                context_units = data
            else:
                raise ValueError("Input JSON must be a list or object with 'context_units'")
    else:
        # Demo with sample data
        context_units = [
            {
                "id": "system",
                "type": "system",
                "content": "You are a helpful coding assistant.",
                "priority": 100
            },
            {
                "id": "user_request",
                "type": "message",
                "content": "Help me implement a cache decorator.",
                "priority": 95
            },
            {
                "id": "example_file",
                "type": "file",
                "content": "def example():\n    pass\n" * 100,
                "priority": 50
            }
        ]
        if not args.quiet:
            print("No input file specified, using demo context", file=sys.stderr)

    resolved_variant = _resolve_experiment_variant(
        experiment_id=args.experiment_id,
        requested_variant=args.variant,
        assignment_key=args.assignment_key
    )
    control_mode = bool(args.experiment_id and resolved_variant == "control")
    tiered_enabled = args.tiered and not args.no_tiered and not control_mode
    relevance_enabled = args.relevance and not args.no_relevance and not control_mode
    apply_pruning = not control_mode

    if control_mode and not args.quiet:
        print(
            "Experiment control variant active: filtering, relevance/tiered assists, and pruning are disabled.",
            file=sys.stderr
        )
    
    # Generate plan
    plan = create_execution_plan(
        context_units=context_units,
        budget=args.budget,
        intent=args.intent,
        target_model=args.model,
        query=args.query,
        prefer_cost_savings=not args.no_cost_optimize,
        auto_filter_packages=not control_mode,
        use_tiered_architecture=tiered_enabled,
        use_relevance_scoring=relevance_enabled,
        track_metrics=args.metrics and not args.no_metrics,
        project_root=args.project_root,
        metrics_dir=args.metrics_dir,
        experiment_id=args.experiment_id,
        experiment_variant=resolved_variant,
        assignment_key=args.assignment_key,
        apply_pruning=apply_pruning,
    )
    
    # Write output
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(plan, f, indent=2)
    
    if not args.quiet:
        print(f"Execution plan generated: {output_path}")
        print(f"  Intent: {plan['constraints']['intent']}")
        print(f"  Model: {plan['recommendations']['model']['recommended']}")
        if plan.get("experiment", {}).get("enabled"):
            print(
                f"  Experiment: {plan['experiment']['id']} ({plan['experiment']['variant']})"
            )
        print(f"  Tokens: {plan['statistics']['input_tokens']} → {plan['statistics']['output_tokens']}")
        print(f"  Saved: {plan['statistics']['tokens_saved']} ({plan['statistics']['reduction_percentage']}%)")
        print(f"  Units: {plan['statistics']['units_kept']} kept, {plan['statistics']['units_pruned']} pruned")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
