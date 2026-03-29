#!/usr/bin/env python3
"""
Generic case runner — reads a YAML case file and runs the full adversarial pipeline.

Usage:
    python scripts/run_case.py cases/wang_zhang_2022.yaml
    python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml --model claude-sonnet-4-6
    python scripts/run_case.py cases/my_case.yaml --claude-only

Output:
    outputs/<timestamp>/result.json
    outputs/<timestamp>/report.md
    outputs/<timestamp>/decision_tree.json
    outputs/<timestamp>/executive_summary.json
    outputs/<timestamp>/attack_chain.json
    outputs/<timestamp>/amount_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

# Windows UTF-8 guard
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import yaml

# Engine imports
from engines.adversarial.agents.defendant import DefendantAgent
from engines.adversarial.agents.evidence_mgr import EvidenceManagerAgent
from engines.adversarial.agents.plaintiff import PlaintiffAgent
from engines.adversarial.round_engine import RoundEngine
from engines.adversarial.schemas import AdversarialResult, RoundConfig, RoundPhase, RoundState
from engines.adversarial.summarizer import AdversarialSummarizer
from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.case_structuring.issue_extractor.extractor import IssueExtractor
from engines.shared.access_control import AccessController
from engines.shared.cli_adapter import CLINotFoundError, ClaudeCLIClient, CodexCLIClient
from engines.shared.models import (
    AgentRole, ClaimType, DisputedAmountAttribution,
    EvidenceIndex, LoanTransaction, RawMaterial,
    RepaymentAttribution, RepaymentTransaction,
)

# Post-debate modules
from engines.case_structuring.amount_calculator import AmountCalculator, AmountCalculatorInput, AmountClaimDescriptor
from engines.simulation_run.issue_impact_ranker.ranker import IssueImpactRanker
from engines.simulation_run.issue_impact_ranker.schemas import IssueImpactRankerInput
from engines.simulation_run.decision_path_tree import DecisionPathTreeGenerator, DecisionPathTreeInput
from engines.simulation_run.attack_chain_optimizer import AttackChainOptimizer, AttackChainOptimizerInput
from engines.simulation_run.action_recommender import ActionRecommender
from engines.simulation_run.action_recommender.schemas import ActionRecommenderInput
from engines.report_generation.executive_summarizer import ExecutiveSummarizer
from engines.report_generation.executive_summarizer.schemas import ExecutiveSummarizerInput


DEFAULT_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# YAML -> typed objects
# ---------------------------------------------------------------------------

def _load_case(path: Path) -> dict[str, Any]:
    """Load and validate a YAML case file."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    required = ["case_id", "case_slug", "case_type", "parties", "materials", "claims", "defenses"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"YAML missing required keys: {missing}")
    return data


def _build_materials(raw_list: list[dict]) -> list[RawMaterial]:
    """Convert YAML material dicts to RawMaterial objects."""
    return [
        RawMaterial(
            source_id=m["source_id"],
            text=m["text"].strip() if isinstance(m["text"], str) else str(m["text"]),
            metadata=m.get("metadata", {}),
        )
        for m in raw_list
    ]


def _build_claims(claim_list: list[dict], case_id: str, plaintiff_id: str) -> list[dict]:
    """Add case_id and owner_party_id to claim dicts."""
    return [
        {**c, "case_id": case_id, "owner_party_id": plaintiff_id}
        for c in claim_list
    ]


def _build_defenses(defense_list: list[dict], case_id: str, defendant_id: str) -> list[dict]:
    """Add case_id and owner_party_id to defense dicts."""
    return [
        {**d, "case_id": case_id, "owner_party_id": defendant_id}
        for d in defense_list
    ]


def _build_financials(
    fin: dict[str, Any], case_id: str, run_id: str,
) -> AmountCalculatorInput | None:
    """Convert YAML financials section to AmountCalculatorInput. Returns None if no financials."""
    if not fin:
        return None

    loans = []
    for tx in fin.get("loans", []):
        loans.append(LoanTransaction(
            tx_id=tx["tx_id"],
            date=tx["date"],
            amount=Decimal(str(tx["amount"])),
            evidence_id=tx["evidence_id"],
            principal_base_contribution=tx.get("principal_base_contribution", True),
        ))

    if not loans:
        return None  # AmountCalculator requires at least 1 loan

    repayments = []
    for tx in fin.get("repayments", []):
        attr = tx.get("attributed_to")
        repayments.append(RepaymentTransaction(
            tx_id=tx["tx_id"],
            date=tx["date"],
            amount=Decimal(str(tx["amount"])),
            evidence_id=tx["evidence_id"],
            attributed_to=RepaymentAttribution(attr) if attr else None,
            attribution_basis=tx.get("attribution_basis", ""),
        ))

    disputed = []
    for d in fin.get("disputed", []):
        disputed.append(DisputedAmountAttribution(
            item_id=d["item_id"],
            amount=Decimal(str(d["amount"])),
            dispute_description=d["dispute_description"],
            plaintiff_attribution=d.get("plaintiff_attribution", ""),
            defendant_attribution=d.get("defendant_attribution", ""),
        ))

    claim_entries = []
    for ce in fin.get("claim_entries", []):
        claim_entries.append(AmountClaimDescriptor(
            claim_id=ce["claim_id"],
            claim_type=ClaimType(ce["claim_type"]),
            claimed_amount=Decimal(str(ce["claimed_amount"])),
            evidence_ids=ce.get("evidence_ids", []),
        ))

    if not claim_entries:
        return None

    source_ids = [tx.evidence_id for tx in loans]
    return AmountCalculatorInput(
        case_id=case_id,
        run_id=run_id,
        source_material_ids=list(set(source_ids)),
        claim_entries=claim_entries,
        loan_transactions=loans,
        repayment_transactions=repayments,
        disputed_amount_attributions=disputed,
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _output_dir() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    d = _PROJECT_ROOT / "outputs" / ts
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(out: Path, result: AdversarialResult) -> Path:
    p = out / "result.json"
    p.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return p


def _write_md(
    out: Path,
    result: AdversarialResult,
    issue_tree,
    case_data: dict,
    *,
    ranked_issues=None,
    decision_tree=None,
    attack_chain=None,
    action_rec=None,
    exec_summary=None,
) -> Path:
    p = out / "report.md"
    lines = [
        "# " + case_data.get("case_type", "civil_loan").replace("_", " ").title() + " Case Report",
        "",
        f"**Case ID**: {result.case_id}  |  **Run ID**: {result.run_id}",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    # Summary table from YAML
    summary_rows = case_data.get("summary", [])
    if summary_rows:
        lines += ["## Case Summary", "", "| Item | Details |", "|------|---------|"]
        for row in summary_rows:
            if isinstance(row, list) and len(row) >= 2:
                lines.append(f"| {row[0]} | {row[1]} |")
        lines.append("")

    # Issue list (ranked if available)
    lines += ["## Issues", ""]
    display_issues = ranked_issues.issues if ranked_issues else issue_tree.issues
    for iss in display_issues:
        impact_tag = f" **{iss.outcome_impact.value}**" if getattr(iss, "outcome_impact", None) else ""
        action_tag = f" [{iss.recommended_action.value}]" if getattr(iss, "recommended_action", None) else ""
        lines.append(f"- **[{iss.issue_id}]** {iss.title} `{iss.issue_type.value}`{impact_tag}{action_tag}")
    lines += [""]

    # Three-round debate
    lines += ["## Adversarial Debate (3 Rounds)", ""]
    for rs in result.rounds:
        lines.append(f"### Round {rs.round_number} ({rs.phase.value})")
        lines.append("")
        for o in rs.outputs:
            lines += [
                f"**{o.agent_role_code}** \u2014 {o.title}", "",
                o.body, "",
                f"*Evidence cited*: {', '.join(o.evidence_citations)}",
                "---", "",
            ]

    # Evidence conflicts
    if result.evidence_conflicts:
        lines += ["## Evidence Conflicts", ""]
        for c in result.evidence_conflicts:
            lines.append(f"- `{c.issue_id}`: {c.conflict_description}")
        lines.append("")

    # Missing evidence
    if result.missing_evidence_report:
        lines += ["## Missing Evidence", ""]
        for m in result.missing_evidence_report:
            lines.append(f"- **[{m.issue_id}]** `{m.missing_for_party_id}`: {m.description}")
        lines.append("")

    # LLM summary
    if result.summary:
        s = result.summary
        lines += ["## LLM Analysis", "", "### Plaintiff Strongest Arguments", ""]
        for a in s.plaintiff_strongest_arguments:
            lines += [f"**[{a.issue_id}]** {a.position}", f"> {a.reasoning}", ""]
        lines += ["### Defendant Strongest Defenses", ""]
        for d in s.defendant_strongest_defenses:
            lines += [f"**[{d.issue_id}]** {d.position}", f"> {d.reasoning}", ""]
        lines += ["### Overall Assessment", "", s.overall_assessment, ""]

    # Issue impact ranking table
    if ranked_issues:
        lines += ["## Issue Impact Ranking", ""]
        lines.append("| Issue | Title | Impact | Attack | Evidence | Action |")
        lines.append("|-------|-------|--------|--------|----------|--------|")
        for iss in ranked_issues.issues:
            impact = iss.outcome_impact.value if iss.outcome_impact else "-"
            attack = iss.opponent_attack_strength.value if iss.opponent_attack_strength else "-"
            ev_str = iss.proponent_evidence_strength.value if iss.proponent_evidence_strength else "-"
            action = iss.recommended_action.value if iss.recommended_action else "-"
            lines.append(f"| {iss.issue_id} | {iss.title[:25]} | {impact} | {attack} | {ev_str} | {action} |")
        lines.append("")

    # Decision path tree
    if decision_tree:
        lines += ["## Decision Path Tree", ""]
        for path in decision_tree.paths:
            lines.append(f"### Path {path.path_id}")
            lines.append(f"**Trigger**: {path.trigger_condition}")
            lines.append(f"**Issues**: {', '.join(path.trigger_issue_ids)}")
            lines.append(f"**Key Evidence**: {', '.join(path.key_evidence_ids)}")
            lines.append(f"**Outcome**: {path.possible_outcome}")
            if path.confidence_interval:
                ci = path.confidence_interval
                lines.append(f"**Confidence**: {ci.low:.0%} ~ {ci.high:.0%}")
            if path.path_notes:
                lines.append(f"**Notes**: {path.path_notes}")
            lines.append("")
        if decision_tree.blocking_conditions:
            lines += ["### Blocking Conditions", ""]
            for bc in decision_tree.blocking_conditions:
                lines.append(f"- **{bc.condition_id}**: {bc.description}")
            lines.append("")

    # Attack chain
    if attack_chain:
        lines += ["## Adversary Optimal Attack Chain", ""]
        lines.append(f"**Attacker**: {attack_chain.owner_party_id}  |  **Order**: {' -> '.join(attack_chain.recommended_order)}")
        lines.append("")
        for node in attack_chain.top_attacks:
            lines.append(f"### {node.attack_node_id}")
            lines.append(f"**Target**: {node.target_issue_id}")
            lines.append(f"**Attack**: {node.attack_description}")
            lines.append(f"**Success condition**: {node.success_conditions}")
            lines.append(f"**Evidence**: {', '.join(node.supporting_evidence_ids)}")
            lines.append(f"**Counter-measure**: {node.counter_measure}")
            lines.append(f"**Pivot strategy**: {node.adversary_pivot_strategy}")
            lines.append("")

    # Action recommendations
    if action_rec:
        lines += ["## Action Recommendations", ""]
        if action_rec.claims_to_abandon:
            lines.append("### Claims to Abandon")
            for ab in action_rec.claims_to_abandon:
                lines.append(f"- **{ab.suggestion_id}** ({ab.claim_id}): {ab.abandon_reason}")
            lines.append("")
        if action_rec.recommended_claim_amendments:
            lines.append("### Claim Amendments")
            for am in action_rec.recommended_claim_amendments:
                lines.append(f"- **{am.suggestion_id}** ({am.original_claim_id}): {am.amendment_description}")
            lines.append("")
        if action_rec.evidence_supplement_priorities:
            lines.append("### Evidence Supplement Priorities")
            for gap_id in action_rec.evidence_supplement_priorities:
                lines.append(f"- {gap_id}")
            lines.append("")
        if action_rec.trial_explanation_priorities:
            lines.append("### Trial Explanation Priorities")
            for tp in action_rec.trial_explanation_priorities:
                lines.append(f"- **{tp.priority_id}** ({tp.issue_id}): {tp.explanation_text}")
            lines.append("")

    # Executive summary
    if exec_summary:
        lines += ["## Executive Summary", ""]
        lines.append(f"**Top 5 decisive issues**: {', '.join(exec_summary.top5_decisive_issues)}")
        lines.append("")
        if isinstance(exec_summary.top3_immediate_actions, list):
            lines.append(f"**Top 3 immediate actions**: {', '.join(exec_summary.top3_immediate_actions)}")
        else:
            lines.append(f"**Top 3 immediate actions**: {exec_summary.top3_immediate_actions}")
        lines.append("")
        lines.append(f"**Top 3 adversary attacks**: {', '.join(exec_summary.top3_adversary_optimal_attacks)}")
        lines.append("")
        lines.append(f"**Most stable claim**: {exec_summary.current_most_stable_claim}")
        lines.append("")
        if isinstance(exec_summary.critical_evidence_gaps, list):
            lines.append(f"**Critical evidence gaps**: {', '.join(exec_summary.critical_evidence_gaps) if exec_summary.critical_evidence_gaps else 'None'}")
        else:
            lines.append(f"**Critical evidence gaps**: {exec_summary.critical_evidence_gaps}")
        lines.append("")

    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Three-round orchestration
# ---------------------------------------------------------------------------

async def _run_rounds(
    issue_tree,
    evidence_index: EvidenceIndex,
    p_client,
    d_client,
    j_client,
    config: RoundConfig,
    plaintiff_id: str,
    defendant_id: str,
) -> AdversarialResult:
    """Run 3-round adversarial debate."""
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    case_id = issue_tree.case_id

    plaintiff = PlaintiffAgent(p_client, plaintiff_id, config)
    defendant = DefendantAgent(d_client, defendant_id, config)
    ev_mgr = EvidenceManagerAgent(j_client, config)

    ac = AccessController()
    p_ev = ac.filter_evidence_for_agent(
        role_code=AgentRole.plaintiff_agent.value,
        owner_party_id=plaintiff_id,
        all_evidence=evidence_index.evidence,
    )
    d_ev = ac.filter_evidence_for_agent(
        role_code=AgentRole.defendant_agent.value,
        owner_party_id=defendant_id,
        all_evidence=evidence_index.evidence,
    )
    print(f"  Plaintiff evidence: {len(p_ev)}  |  Defendant evidence: {len(d_ev)}")

    rounds, all_out, conflicts = [], [], []

    # Round 1: Opening claims
    print("\n[R1] Opening claims...")
    sid1 = f"state-r1-{uuid.uuid4().hex[:8]}"
    p1 = await plaintiff.generate_claim(issue_tree, p_ev, [], run_id, sid1, 1)
    p1 = p1.model_copy(update={"case_id": case_id})
    print(f"  \u2713 Plaintiff: {p1.title}")
    d1 = await defendant.generate_claim(issue_tree, d_ev, [p1], run_id, sid1, 1)
    d1 = d1.model_copy(update={"case_id": case_id})
    print(f"  \u2713 Defendant: {d1.title}")
    rounds.append(RoundState(round_number=1, phase=RoundPhase.claim, outputs=[p1, d1]))
    all_out += [p1, d1]

    # Round 2: Evidence review
    print("\n[R2] Evidence review...")
    sid2 = f"state-r2-{uuid.uuid4().hex[:8]}"
    ev_out, new_conf = await ev_mgr.analyze(
        issue_tree, evidence_index, [p1], [d1], run_id, sid2, 2,
    )
    ev_out = ev_out.model_copy(update={"case_id": case_id})
    conflicts += new_conf
    print(f"  \u2713 Evidence manager: {ev_out.title}  ({len(new_conf)} conflicts)")
    rounds.append(RoundState(round_number=2, phase=RoundPhase.evidence, outputs=[ev_out]))
    all_out.append(ev_out)

    # Round 3: Rebuttals
    print("\n[R3] Rebuttals...")
    sid3 = f"state-r3-{uuid.uuid4().hex[:8]}"
    p3 = await plaintiff.generate_rebuttal(issue_tree, p_ev, all_out, [d1], run_id, sid3, 3)
    p3 = p3.model_copy(update={"case_id": case_id})
    print(f"  \u2713 Plaintiff rebuttal: {p3.title}")
    d3 = await defendant.generate_rebuttal(issue_tree, d_ev, all_out, [p1], run_id, sid3, 3)
    d3 = d3.model_copy(update={"case_id": case_id})
    print(f"  \u2713 Defendant rebuttal: {d3.title}")
    rounds.append(RoundState(round_number=3, phase=RoundPhase.rebuttal, outputs=[p3, d3]))
    all_out += [p3, d3]

    p_best = RoundEngine._extract_best_arguments(p1, p3)
    d_best = RoundEngine._extract_best_arguments(d1, d3)
    unresolved = RoundEngine._compute_unresolved_issues(issue_tree, conflicts)
    missing = RoundEngine._build_missing_evidence_report(
        issue_tree, p_ev, d_ev, plaintiff_id, defendant_id,
    )

    result = AdversarialResult(
        case_id=case_id, run_id=run_id, rounds=rounds,
        plaintiff_best_arguments=p_best, defendant_best_defenses=d_best,
        unresolved_issues=unresolved, evidence_conflicts=conflicts,
        missing_evidence_report=missing,
    )

    # LLM summarizer
    print("\n[Summary] Generating LLM analysis...")
    summarizer = AdversarialSummarizer(j_client, config)
    summary = await summarizer.summarize(result, issue_tree)
    return result.model_copy(update={"summary": summary})


# ---------------------------------------------------------------------------
# Post-debate analysis pipeline
# ---------------------------------------------------------------------------

async def _run_post_debate(
    result: AdversarialResult,
    issue_tree,
    ev_index: EvidenceIndex,
    llm_client,
    case_data: dict,
    model: str,
) -> dict[str, Any]:
    """Run post-debate analysis pipeline. Returns dict of all artifacts."""
    case_id = case_data["case_id"]
    run_id = result.run_id
    p_id = case_data["parties"]["plaintiff"]["party_id"]
    d_id = case_data["parties"]["defendant"]["party_id"]

    artifacts: dict[str, Any] = {}

    # P0.2: AmountCalculator (sync, rule-based)
    amount_input = _build_financials(case_data.get("financials", {}), case_id, run_id)
    if amount_input:
        print("  - Amount consistency check...")
        amount_report = AmountCalculator().calculate(amount_input)
        artifacts["amount_report"] = amount_report
        vb = amount_report.consistency_check_result.verdict_block_active
        uc = len(amount_report.consistency_check_result.unresolved_conflicts)
        print(f"    \u2713 Verdict block: {vb}  |  Unresolved conflicts: {uc}")
    else:
        print("  - No financials in YAML, skipping amount calculator")
        amount_report = None

    # P0.1: IssueImpactRanker (LLM)
    if amount_report:
        print("  - Issue impact ranking...")
        ranker = IssueImpactRanker(
            llm_client=llm_client, model=model,
            temperature=0.0, max_retries=2,
        )
        ranking_result = await ranker.rank(IssueImpactRankerInput(
            case_id=case_id, run_id=run_id,
            issue_tree=issue_tree,
            evidence_index=ev_index,
            amount_calculation_report=amount_report,
            proponent_party_id=p_id,
        ))
        ranked_tree = ranking_result.ranked_issue_tree
        artifacts["ranked_issues"] = ranked_tree
        print(f"    \u2713 Ranked issues: {len(ranked_tree.issues)}")
        for iss in ranked_tree.issues:
            tag = iss.outcome_impact.value if iss.outcome_impact else "?"
            print(f"      [{tag}] {iss.issue_id}: {iss.title}")
    else:
        ranked_tree = issue_tree
        artifacts["ranked_issues"] = None

    # P0.3 + P0.4: DecisionPathTree + AttackChainOptimizer (parallel, LLM)
    if amount_report:
        print("  - Decision path tree + attack chain...")
        dpt_gen = DecisionPathTreeGenerator(
            llm_client=llm_client, model=model,
            temperature=0.0, max_retries=2,
        )
        aco = AttackChainOptimizer(
            llm_client=llm_client, model=model,
            temperature=0.0, max_retries=2,
        )
        decision_tree, attack_chain = await asyncio.gather(
            dpt_gen.generate(DecisionPathTreeInput(
                case_id=case_id, run_id=run_id,
                ranked_issue_tree=ranked_tree,
                evidence_index=ev_index,
                amount_calculation_report=amount_report,
            )),
            aco.optimize(AttackChainOptimizerInput(
                case_id=case_id, run_id=run_id,
                owner_party_id=d_id,
                issue_tree=ranked_tree,
                evidence_index=ev_index,
            )),
        )
        artifacts["decision_tree"] = decision_tree
        artifacts["attack_chain"] = attack_chain
        print(f"    \u2713 Decision paths: {len(decision_tree.paths)}")
        print(f"    \u2713 Attack nodes: {len(attack_chain.top_attacks)}")
    else:
        decision_tree = None
        attack_chain = None

    # P1.8: ActionRecommender (sync, rule-based)
    if amount_report and attack_chain:
        print("  - Action recommendations...")
        action_rec = ActionRecommender().recommend(ActionRecommenderInput(
            case_id=case_id, run_id=run_id,
            issue_list=ranked_tree.issues,
            evidence_gap_list=[],
            amount_calculation_report=amount_report,
        ))
        artifacts["action_rec"] = action_rec
        print(f"    \u2713 Amendments: {len(action_rec.recommended_claim_amendments)}")
        print(f"    \u2713 Abandon: {len(action_rec.claims_to_abandon)}")
    else:
        action_rec = None

    # P2.12: ExecutiveSummarizer (sync, rule-based)
    if amount_report and attack_chain:
        print("  - Executive summary...")
        exec_summary = ExecutiveSummarizer().summarize(ExecutiveSummarizerInput(
            case_id=case_id, run_id=run_id,
            issue_list=ranked_tree.issues,
            adversary_attack_chain=attack_chain,
            amount_calculation_report=amount_report,
            action_recommendation=action_rec,
            evidence_gap_items=None,
        ))
        artifacts["exec_summary"] = exec_summary
        print(f"    \u2713 Top 5 issues: {exec_summary.top5_decisive_issues}")
    else:
        exec_summary = None

    return artifacts


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(case_path: str, model_override: str | None = None, claude_only: bool = False) -> None:
    case_file = Path(case_path)
    if not case_file.exists():
        print(f"[Error] Case file not found: {case_file}")
        sys.exit(1)

    case_data = _load_case(case_file)
    case_id = case_data["case_id"]
    case_slug = case_data["case_slug"]
    case_type = case_data.get("case_type", "civil_loan")
    model = model_override or case_data.get("model", DEFAULT_MODEL)
    p_id = case_data["parties"]["plaintiff"]["party_id"]
    d_id = case_data["parties"]["defendant"]["party_id"]
    p_name = case_data["parties"]["plaintiff"].get("name", p_id)
    d_name = case_data["parties"]["defendant"].get("name", d_id)

    print("=" * 60)
    print(f"Case: {case_id}")
    print(f"Parties: {p_name} (plaintiff) vs {d_name} (defendant)")
    print(f"Model: {model}")
    print("=" * 60)

    # LLM clients
    claude = ClaudeCLIClient(timeout=600.0)
    if claude_only:
        print("\n[Config] All agents use Claude CLI (--claude-only)")
        codex = claude
    else:
        import shutil as _sh
        if not _sh.which("codex"):
            print("\n[Config] codex not in PATH, all agents use Claude CLI")
            codex = claude
        else:
            print("\n[Config] Plaintiff/Evidence/Summary -> Claude  |  Defendant -> Codex")
            codex = CodexCLIClient(timeout=600.0)

    # Step 1: Index evidence
    print("\n[Step 1] Indexing evidence...")
    indexer = EvidenceIndexer(llm_client=claude, case_type=case_type, model=model, max_retries=2)
    p_materials = _build_materials(case_data["materials"]["plaintiff"])
    d_materials = _build_materials(case_data["materials"]["defendant"])
    p_ev = await indexer.index(p_materials, case_id, p_id, "plaintiff")
    print(f"  \u2713 Plaintiff evidence: {len(p_ev)}")
    d_ev = await indexer.index(d_materials, case_id, d_id, "defendant")
    print(f"  \u2713 Defendant evidence: {len(d_ev)}")
    all_ev = p_ev + d_ev
    ev_index = EvidenceIndex(case_id=case_id, evidence=all_ev)
    print(f"  \u2713 Total evidence: {len(all_ev)}")

    # Step 2: Extract issue tree
    print("\n[Step 2] Extracting issues...")
    extractor = IssueExtractor(llm_client=claude, case_type=case_type, model=model, max_retries=2)
    ev_dicts = [e.model_dump() for e in all_ev]
    claims = _build_claims(case_data["claims"], case_id, p_id)
    defenses = _build_defenses(case_data["defenses"], case_id, d_id)
    issue_tree = await extractor.extract(claims, defenses, ev_dicts, case_id, case_slug)
    print(f"  \u2713 Issues: {len(issue_tree.issues)}  |  Burdens: {len(issue_tree.burdens)}")
    for iss in issue_tree.issues:
        print(f"    - [{iss.issue_id}] {iss.title}")

    # Step 3: Three-round adversarial debate
    print("\n[Step 3] Three-round adversarial debate...")
    config = RoundConfig(model=model, max_tokens_per_output=2000, max_retries=2)
    result = await _run_rounds(
        issue_tree, ev_index, claude, codex, claude, config, p_id, d_id,
    )

    # Step 3.5: Post-debate analysis
    print("\n[Step 3.5] Post-debate analysis...")
    artifacts = await _run_post_debate(result, issue_tree, ev_index, claude, case_data, model)

    # Step 4: Write outputs
    print("\n[Step 4] Writing outputs...")
    out = _output_dir()
    jp = _write_json(out, result)
    mp = _write_md(
        out, result, issue_tree, case_data,
        ranked_issues=artifacts.get("ranked_issues"),
        decision_tree=artifacts.get("decision_tree"),
        attack_chain=artifacts.get("attack_chain"),
        action_rec=artifacts.get("action_rec"),
        exec_summary=artifacts.get("exec_summary"),
    )

    # Serialize post-debate artifacts
    for name in ("decision_tree", "attack_chain", "amount_report", "exec_summary"):
        obj = artifacts.get(name)
        if obj:
            (out / f"{name}.json").write_text(obj.model_dump_json(indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"\u2713 Run complete")
    print(f"  Result JSON: {jp}")
    print(f"  Report:      {mp}")
    for name in ("decision_tree", "attack_chain", "amount_report", "exec_summary"):
        artifact_path = out / f"{name}.json"
        if artifact_path.exists():
            print(f"  {name}: {artifact_path}")
    if result.summary:
        print(f"\nOverall assessment:")
        print(f"  {result.summary.overall_assessment[:300]}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run adversarial case analysis from a YAML case file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python scripts/run_case.py cases/wang_zhang_2022.yaml --model claude-opus-4-6",
    )
    parser.add_argument("case_file", help="Path to YAML case definition file")
    parser.add_argument("--model", default=None, help="Override LLM model (default: from YAML or claude-sonnet-4-6)")
    parser.add_argument("--claude-only", action="store_true", help="Use Claude CLI for all agents (skip Codex)")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.case_file, model_override=args.model, claude_only=args.claude_only))
    except CLINotFoundError as e:
        print(f"\n[Error] CLI not available: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Interrupted] User cancelled.")
        sys.exit(0)
