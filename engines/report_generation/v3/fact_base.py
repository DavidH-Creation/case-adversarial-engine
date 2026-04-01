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

    Strategy:
    1. Evidence with no challenges → fact about its existence
    2. FactPropositions with status='supported' → established facts
    3. Transfer records / bank records → financial facts
    4. Identity information → party facts

    Args:
        issue_tree: IssueTree from pipeline
        evidence_index: EvidenceIndex from pipeline
        adversarial_result: AdversarialResult (optional, for conflict filtering)

    Returns:
        List of FactBaseEntry representing undisputed facts
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

    # 1. Extract facts from unchallenged evidence
    for ev in evidence_index.evidence:
        is_challenged = bool(getattr(ev, "challenged_by_party_ids", []))
        if is_challenged or ev.evidence_id in disputed_ev_ids:
            continue

        # Documentary and bank records are typically undisputed facts
        ev_type = ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type)
        if ev_type in ("documentary", "physical"):
            fact_counter += 1
            facts.append(FactBaseEntry(
                fact_id=f"FACT-{fact_counter:03d}",
                description=f"{ev.title}：{ev.summary[:200]}",
                source_evidence_ids=[ev.evidence_id],
                tag=SectionTag.fact,
            ))

    # 2. Extract from supported fact propositions
    for issue in issue_tree.issues:
        for prop in getattr(issue, "fact_propositions", []):
            if hasattr(prop, "status") and prop.status.value == "supported":
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
            # Already covered in step 1, but ensure transfer details captured
            if not any(ev.evidence_id in f.source_evidence_ids for f in facts):
                fact_counter += 1
                facts.append(FactBaseEntry(
                    fact_id=f"FACT-{fact_counter:03d}",
                    description=f"转账记录：{ev.summary[:200]}",
                    source_evidence_ids=[ev.evidence_id],
                    tag=SectionTag.fact,
                ))

    return facts
