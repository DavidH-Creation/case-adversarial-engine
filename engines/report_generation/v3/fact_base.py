"""
事实底座提取器 / Fact Base Extractor.

从证据索引和争点树中提取无争议的客观事实。
仅保留双方均不争议的事实命题，不含法律推断。
"""

from __future__ import annotations

from engines.report_generation.v3.models import FactBaseEntry, SectionTag


def extract_fact_base(
    issue_tree,
    evidence_index,
    adversarial_result=None,
) -> list[FactBaseEntry]:
    """Extract undisputed objective facts from case data.

    IMPORTANT: "unchallenged" ≠ "undisputed". A fact is only undisputed if:
    - BOTH sides acknowledge/reference it, OR
    - It is objectively verifiable (bank records, official documents with
      third-party confirmation such as court/notary/government stamps)

    Strategy:
    1. Third-party verifiable evidence (bank/notary/court) → objective facts
    2. Evidence referenced by BOTH parties → mutually acknowledged facts
    3. FactPropositions with status='undisputed' → established facts
    4. Bank transfer records from metadata → financial facts

    Args:
        issue_tree: IssueTree from pipeline
        evidence_index: EvidenceIndex from pipeline
        adversarial_result: AdversarialResult (optional, for conflict filtering
                           and mutual-reference detection)

    Returns:
        List of FactBaseEntry representing truly undisputed facts
    """
    facts: list[FactBaseEntry] = []
    fact_counter = 0

    # Collect disputed evidence IDs from adversarial result
    disputed_ev_ids: set[str] = set()
    if adversarial_result and adversarial_result.evidence_conflicts:
        for conflict in adversarial_result.evidence_conflicts:
            disputed_ev_ids.update(
                getattr(conflict, "evidence_ids", [])
            )

    # Collect evidence IDs referenced by BOTH sides (mutually acknowledged)
    mutually_referenced: set[str] = set()
    if adversarial_result:
        plaintiff_ev: set[str] = set()
        defendant_ev: set[str] = set()
        for arg in (getattr(adversarial_result, "plaintiff_best_arguments", None) or []):
            plaintiff_ev.update(getattr(arg, "supporting_evidence_ids", []))
        if adversarial_result.summary:
            for arg in (adversarial_result.summary.plaintiff_strongest_arguments or []):
                plaintiff_ev.update(getattr(arg, "supporting_evidence_ids", []))
        for arg in (getattr(adversarial_result, "defendant_best_defenses", None) or []):
            defendant_ev.update(getattr(arg, "supporting_evidence_ids", []))
        if adversarial_result.summary:
            for arg in (adversarial_result.summary.defendant_strongest_defenses or []):
                defendant_ev.update(getattr(arg, "supporting_evidence_ids", []))
        mutually_referenced = plaintiff_ev & defendant_ev

    # Third-party verifiable source keywords
    _verifiable_sources = {
        "银行", "bank", "公证", "notary", "法院", "court",
        "工商", "税务", "公安",
    }

    def _is_third_party_verifiable(ev) -> bool:
        """Check if evidence is objectively verifiable by a third party."""
        source_lower = (ev.source + " " + ev.title).lower()
        return any(kw in source_lower for kw in _verifiable_sources)

    # 1. Extract facts from third-party verifiable OR mutually acknowledged evidence
    for ev in evidence_index.evidence:
        is_challenged = bool(getattr(ev, "challenged_by_party_ids", []))
        if is_challenged or ev.evidence_id in disputed_ev_ids:
            continue

        ev_type = ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type)
        is_verifiable = (
            _is_third_party_verifiable(ev)
            and ev_type in ("documentary", "physical")
        )
        is_mutual = ev.evidence_id in mutually_referenced

        if is_verifiable or is_mutual:
            fact_counter += 1
            source_note = "第三方可核实" if is_verifiable else "双方均引用"
            facts.append(FactBaseEntry(
                fact_id=f"FACT-{fact_counter:03d}",
                description=f"{ev.title}：{ev.summary[:200]}（{source_note}）",
                source_evidence_ids=[ev.evidence_id],
                tag=SectionTag.fact,
            ))

    # 2. Extract from fact propositions only if truly undisputed
    for issue in issue_tree.issues:
        for prop in getattr(issue, "fact_propositions", []):
            prop_status = ""
            if hasattr(prop, "status"):
                prop_status = prop.status.value if hasattr(prop.status, "value") else str(prop.status)
            # Only "undisputed" or "supported" with linked evidence that is mutually referenced
            if prop_status == "undisputed":
                fact_counter += 1
                facts.append(FactBaseEntry(
                    fact_id=f"FACT-{fact_counter:03d}",
                    description=prop.text,
                    source_evidence_ids=getattr(prop, "linked_evidence_ids", []),
                    tag=SectionTag.fact,
                ))
            elif prop_status == "supported":
                linked = set(getattr(prop, "linked_evidence_ids", []))
                if linked and linked & mutually_referenced:
                    fact_counter += 1
                    facts.append(FactBaseEntry(
                        fact_id=f"FACT-{fact_counter:03d}",
                        description=prop.text,
                        source_evidence_ids=getattr(prop, "linked_evidence_ids", []),
                        tag=SectionTag.fact,
                    ))

    # 3. Extract financial transfer facts from evidence metadata
    for ev in evidence_index.evidence:
        metadata = getattr(ev, "metadata", {}) or {}
        doc_type = metadata.get("document_type", "")
        if doc_type in ("bank_transfer_records", "payment_records"):
            if not any(ev.evidence_id in f.source_evidence_ids for f in facts):
                # Only include if not disputed
                if ev.evidence_id not in disputed_ev_ids:
                    fact_counter += 1
                    facts.append(FactBaseEntry(
                        fact_id=f"FACT-{fact_counter:03d}",
                        description=f"转账记录：{ev.summary[:200]}（银行记录）",
                        source_evidence_ids=[ev.evidence_id],
                        tag=SectionTag.fact,
                    ))

    return facts
