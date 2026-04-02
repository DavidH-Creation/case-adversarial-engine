"""
engines/shared/display_resolver.py

Centralized ID-to-human-readable-text resolver for pipeline artifacts.

Usage::

    from engines.shared.display_resolver import resolve_gap, resolve_issue, resolve_path

    # Turn a raw gap_id into a description
    desc = resolve_gap("xexam-EV001-ISS001", evidence_gaps)

    # Turn a raw path_id into an outcome summary
    outcome = resolve_path("PATH-A", decision_tree)

All functions are pure (no side-effects) and safe to call with None inputs;
they fall back gracefully to returning the raw ID when no match is found.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from engines.shared.models import (
        EvidenceGapItem,
        Issue,
    )
    from engines.shared.models.pipeline import DecisionPathTree


# ---------------------------------------------------------------------------
# Evidence gap resolution
# ---------------------------------------------------------------------------


def resolve_gap(gap_id: str, evidence_gaps: "list[EvidenceGapItem]") -> str:
    """Resolve a gap_id to its human-readable description.

    Args:
        gap_id:        The internal gap identifier (e.g. "missing-ISS001-p001").
        evidence_gaps: The list of EvidenceGapItem objects produced by P1.7.

    Returns:
        The ``gap_description`` of the matching item, or *gap_id* if not found.
    """
    for gap in evidence_gaps:
        if gap.gap_id == gap_id:
            return gap.gap_description
    return gap_id


# ---------------------------------------------------------------------------
# Issue resolution
# ---------------------------------------------------------------------------


def resolve_issue(issue_id: str, issues: "list[Issue]") -> str:
    """Resolve an issue_id to its title.

    Args:
        issue_id: The internal issue identifier (e.g. "ISS001").
        issues:   A flat list of Issue objects.

    Returns:
        The ``title`` of the matching Issue, or *issue_id* if not found.
    """
    for issue in issues:
        if issue.issue_id == issue_id:
            return issue.title
    return issue_id


# ---------------------------------------------------------------------------
# Decision path resolution
# ---------------------------------------------------------------------------


def resolve_path(path_id: str, decision_tree: "Optional[DecisionPathTree]") -> str:
    """Resolve a path_id to a human-readable outcome summary.

    Includes the probability estimate when available (e.g. "原告全额支持 (72%)").

    Args:
        path_id:       The internal path identifier.
        decision_tree: The DecisionPathTree artifact from P0.3.

    Returns:
        A formatted string combining ``possible_outcome`` and probability,
        or *path_id* if the tree is None or the path is not found.
    """
    if decision_tree is None:
        return path_id
    for path in decision_tree.paths:
        if path.path_id == path_id:
            return path.possible_outcome
    return path_id


# ---------------------------------------------------------------------------
# Batch gap resolution (for report sections)
# ---------------------------------------------------------------------------


def resolve_gaps_bulk(
    gap_ids: "list[str]",
    evidence_gaps: "list[EvidenceGapItem]",
) -> "list[tuple[str, str]]":
    """Resolve a list of gap_ids to (gap_id, description) pairs.

    Args:
        gap_ids:       Ordered list of gap identifiers (from ActionRecommendation).
        evidence_gaps: The EvidenceGapItem list produced by P1.7.

    Returns:
        List of (gap_id, description) tuples in the same order as *gap_ids*.
        Items not found in evidence_gaps retain the raw ID as their description.
    """
    gap_map = {g.gap_id: g.gap_description for g in evidence_gaps}
    return [(gid, gap_map.get(gid, gid)) for gid in gap_ids]
