"""
争点抽取器核心模块
Issue extractor core module

从 Claims + Defenses + Evidence 中提取争议焦点，构建争点树，
并为每个核心争点分配举证责任。

Extracts disputed issues from Claims + Defenses + Evidence,
builds an issue tree, and assigns burden of proof to core issues.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from engines.shared.json_utils import _extract_json_object  # noqa: F401 (re-exported for tests)
from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .schemas import (
    Burden,
    BurdenStatus,
    ClaimIssueMapping,
    DefenseIssueMapping,
    ExtractionMetadata,
    FactProposition,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    LLMExtractionOutput,
    PropositionStatus,
)

# tool_use 模式的 JSON Schema（源自 LLMExtractionOutput，在模块加载时计算一次）
# JSON Schema for tool_use mode, derived from LLMExtractionOutput at import time
_TOOL_SCHEMA: dict = LLMExtractionOutput.model_json_schema()


# ---------------------------------------------------------------------------
# 解析工具函数 / Parsing utilities
# ---------------------------------------------------------------------------


def _resolve_issue_type(raw_type: str) -> IssueType:
    """将 LLM 返回的争点类型字符串解析为枚举值。
    Resolve LLM-returned issue type string to IssueType enum value.

    支持英文枚举值和中文描述。
    Supports both English enum values and Chinese descriptions.
    """
    _MAP: dict[str, IssueType] = {
        "factual": IssueType.factual,
        "事实争点": IssueType.factual,
        "legal": IssueType.legal,
        "法律争点": IssueType.legal,
        "procedural": IssueType.procedural,
        "程序争点": IssueType.procedural,
        "mixed": IssueType.mixed,
        "混合争点": IssueType.mixed,
    }
    normalized = raw_type.strip().lower()
    return _MAP.get(normalized, _MAP.get(raw_type.strip(), IssueType.factual))


def _resolve_proposition_status(raw: str) -> PropositionStatus:
    """将 LLM 返回的命题状态字符串解析为枚举值。
    Resolve LLM-returned proposition status string to PropositionStatus enum.
    """
    try:
        return PropositionStatus(raw.strip().lower())
    except ValueError:
        return PropositionStatus.unverified


# ---------------------------------------------------------------------------
# 主引擎类 / Main engine class
# ---------------------------------------------------------------------------


class IssueExtractor:
    """争点抽取器
    Issue Extractor

    将 Claims + Defenses + Evidence 通过 LLM 提取为结构化 IssueTree。
    Extracts a structured IssueTree from Claims + Defenses + Evidence via LLM.

    Args:
        llm_client: 符合 LLMClient 协议的客户端实例 / LLMClient-compatible client instance
        case_type: 案由类型，用于选择 prompt 模板，默认 "civil_loan"
                   Case type for prompt template selection, default "civil_loan"
        model: LLM 模型名称 / LLM model name
        temperature: LLM 温度参数，结构化提取建议用 0.0 / LLM temperature (0.0 for structured output)
        max_tokens: LLM 最大输出 token 数 / Max tokens for LLM output
        max_retries: LLM 调用失败时的最大重试次数 / Max retries on LLM call failure
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ) -> None:
        self._llm_client = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """加载案由对应的 prompt 模板模块。
        Load the prompt template module for the given case type.

        使用注册表模式，支持动态扩展新案由。
        Uses a registry pattern for dynamic extension with new case types.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"不支持的案由类型 / Unsupported case type: '{case_type}'。"
                f"可用类型 / Available: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(
        self,
        claims: list[dict],
        defenses: list[dict],
        evidence: list[dict],
    ) -> None:
        """验证输入数据合法性。
        Validate input data validity.

        Raises:
            ValueError: claims 为空、claim_id 重复或 defense_id 重复时抛出。
                        Raised when claims is empty, or IDs are duplicated.
        """
        if not claims:
            raise ValueError("claims 列表不能为空 / claims list cannot be empty")

        # 检查 claim_id 唯一性 / Check claim_id uniqueness
        seen_cids: set[str] = set()
        dup_cids: set[str] = set()
        for c in claims:
            cid = c.get("claim_id", "")
            if cid in seen_cids:
                dup_cids.add(cid)
            seen_cids.add(cid)
        if dup_cids:
            raise ValueError(f"存在重复的 claim_id / Duplicate claim_id: {dup_cids}")

        # 检查 defense_id 唯一性 / Check defense_id uniqueness
        if defenses:
            seen_dids: set[str] = set()
            dup_dids: set[str] = set()
            for d in defenses:
                did = d.get("defense_id", "")
                if did in seen_dids:
                    dup_dids.add(did)
                seen_dids.add(did)
            if dup_dids:
                raise ValueError(f"存在重复的 defense_id / Duplicate defense_id: {dup_dids}")

    async def extract(
        self,
        claims: list[dict],
        defenses: list[dict],
        evidence: list[dict],
        case_id: str,
        case_slug: str = "case",
    ) -> IssueTree:
        """执行争点抽取。
        Execute issue extraction.

        Args:
            claims: 诉请列表（dict 格式）/ List of claim dicts
            defenses: 抗辩列表（dict 格式）/ List of defense dicts
            evidence: 已索引证据列表（dict 格式）/ List of indexed evidence dicts
            case_id: 案件ID / Case ID
            case_slug: 案件简称，用于生成 issue_id 等 / Case slug for ID generation

        Returns:
            IssueTree 包含结构化争点、举证责任和映射关系。
            IssueTree containing structured issues, burdens, and mappings.

        Raises:
            ValueError: 输入无效或 LLM 响应无法解析 / Invalid input or unparseable LLM response
            RuntimeError: LLM 调用失败且超过最大重试次数 / LLM call failed after max retries
        """
        self._validate_input(claims, defenses, evidence)

        # 构建 prompt / Build prompt
        from .prompts import plugin

        system_prompt = self._prompt_module.SYSTEM_PROMPT
        user_prompt = plugin.get_prompt(
            "issue_extractor",
            self._case_type,
            {
                "case_id": case_id,
                "claims": claims,
                "defenses": defenses,
                "evidence": evidence,
            },
        )

        # 调用 LLM（结构化输出优先，fallback 到 json_utils）
        # Call LLM (structured output first, fallback to json_utils)
        raw_dict = await self._call_llm_structured(system_prompt, user_prompt)
        llm_output = LLMExtractionOutput.model_validate(raw_dict)

        # 构建 IssueTree / Build IssueTree
        return self._build_issue_tree(llm_output, case_id, case_slug, claims, defenses, evidence)

    async def _call_llm_structured(self, system: str, user: str) -> dict:
        """调用 LLM 并返回结构化 dict（tool_use 优先，fallback 到 json_utils）。
        Call LLM and return a structured dict (tool_use first, fallback to json_utils).

        Raises:
            RuntimeError: 超过最大重试次数 / Max retries exceeded
            ValueError:   响应无法解析为 JSON / Response cannot be parsed as JSON
        """
        return await call_structured_llm(
            self._llm_client,
            system=system,
            user=user,
            model=self._model,
            tool_name="extract_issues",
            tool_description="从案件诉请、抗辩和证据中提取结构化争点树、举证责任和映射关系。"
            "Extract a structured issue tree, burdens, and mappings "
            "from legal claims, defenses, and evidence.",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )

    def _build_issue_tree(
        self,
        llm_output: LLMExtractionOutput,
        case_id: str,
        case_slug: str,
        claims: list[dict],
        defenses: list[dict],
        evidence: list[dict],
    ) -> IssueTree:
        """将 LLM 提取的原始结构转化为规范化 IssueTree。
        Transform raw LLM extraction output into a normalized IssueTree.

        强制执行合约不变量：
        Enforces contract invariants:
        - 每个 Claim 至少映射一个 Issue / Each Claim maps to at least one Issue
        - 每个 Defense 至少映射一个 Issue / Each Defense maps to at least one Issue
        - 核心 Issue（无 parent）至少分配一个 Burden / Root issues get at least one Burden
        - 所有内部 ID 引用一致 / All internal ID references are consistent
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 预计算已知 evidence_id 集合，用于校验 issue 中的引用
        # Pre-compute known evidence IDs for reference validation in issues
        known_ev_ids: set[str] = {e["evidence_id"] for e in evidence if "evidence_id" in e}

        # ── 1. 建立 tmp_id → proper_id 映射 ──────────────────────────────────
        # Build tmp_id → proper_id mapping
        tmp_to_proper: dict[str, str] = {}
        for idx, item in enumerate(llm_output.issues, 1):
            proper_id = f"issue-{case_slug}-{idx:03d}"
            key = item.tmp_id or f"tmp-{idx}"
            tmp_to_proper[key] = proper_id
            # 也接受已经是正式格式的 ID / Also accept already-proper IDs
            tmp_to_proper[proper_id] = proper_id

        # ── 2. 预计算每个 issue 对应的 burden_id 列表 ─────────────────────────
        # Pre-compute burden_ids per issue tmp_id
        tmp_to_burden_ids: dict[str, list[str]] = {}
        for b_idx, burden in enumerate(llm_output.burdens, 1):
            bid = f"burden-{case_slug}-{b_idx:03d}"
            key = burden.issue_tmp_id or ""
            tmp_to_burden_ids.setdefault(key, []).append(bid)

        # ── 3. 构建 Issue 列表 ────────────────────────────────────────────────
        # Build Issue list
        issues: list[Issue] = []
        for issue_idx, item in enumerate(llm_output.issues, 1):
            tmp_key = item.tmp_id or f"tmp-{issue_idx}"
            issue_id = tmp_to_proper[tmp_key]

            # 解析 parent_issue_id / Resolve parent_issue_id
            parent_id: Optional[str] = None
            if item.parent_tmp_id:
                parent_id = tmp_to_proper.get(item.parent_tmp_id)

            # 关联的 burden_ids / Associated burden IDs
            burden_ids = tmp_to_burden_ids.get(tmp_key, [])

            # 校验 evidence_ids：仅保留输入中已知的 evidence_id
            # Validate evidence_ids: keep only IDs present in input evidence
            validated_evidence_ids = [eid for eid in item.evidence_ids if eid in known_ev_ids]

            # 构建事实命题（分配正式 proposition_id）
            # Build fact propositions with assigned proposition_ids
            fact_props: list[FactProposition] = []
            for fp_idx, fp in enumerate(item.fact_propositions, 1):
                fact_props.append(
                    FactProposition(
                        proposition_id=f"fp-{case_slug}-{issue_idx:03d}-{fp_idx:02d}",
                        text=fp.text,
                        status=_resolve_proposition_status(fp.status),
                        # 同样只保留已知 evidence_id / Also filter linked_evidence_ids
                        linked_evidence_ids=[
                            eid for eid in fp.linked_evidence_ids if eid in known_ev_ids
                        ],
                    )
                )

            issues.append(
                Issue(
                    issue_id=issue_id,
                    case_id=case_id,
                    title=item.title,
                    issue_type=_resolve_issue_type(item.issue_type),
                    parent_issue_id=parent_id,
                    related_claim_ids=item.related_claim_ids,
                    related_defense_ids=item.related_defense_ids,
                    evidence_ids=validated_evidence_ids,
                    burden_ids=burden_ids,
                    fact_propositions=fact_props,
                    status=IssueStatus.open,
                    created_at=now,
                )
            )

        # ── 4. 构建 Burden 列表 ───────────────────────────────────────────────
        # Build Burden list
        burdens: list[Burden] = []
        for b_idx, b in enumerate(llm_output.burdens, 1):
            issue_id = tmp_to_proper.get(b.issue_tmp_id or "", "")
            burdens.append(
                Burden(
                    burden_id=f"burden-{case_slug}-{b_idx:03d}",
                    case_id=case_id,
                    issue_id=issue_id,
                    burden_party_id=b.burden_party_id or "unknown",
                    description=b.description,
                    proof_standard=b.proof_standard,
                    legal_basis=b.legal_basis,
                    status=BurdenStatus.not_met,
                )
            )

        # ── 4b. 根争点 burden 兜底 / Root issue burden fallback ───────────────
        # 若某个根争点（无 parent）没有 burden，自动生成默认 burden 并更新 issue
        # If a root issue has no burden assigned, generate a default burden
        updated_issues: list[Issue] = []
        b_idx_offset = len(burdens)
        for issue in issues:
            if issue.parent_issue_id is None and not issue.burden_ids:
                b_idx_offset += 1
                fb_bid = f"burden-{case_slug}-{b_idx_offset:03d}"
                burdens.append(
                    Burden(
                        burden_id=fb_bid,
                        case_id=case_id,
                        issue_id=issue.issue_id,
                        burden_party_id="unknown",
                        description=(
                            f"举证责任待分配（{issue.title}）"
                            f"/ Burden of proof pending assignment ({issue.title})"
                        ),
                        proof_standard="",
                        legal_basis="",
                        status=BurdenStatus.not_met,
                    )
                )
                updated_issues.append(issue.model_copy(update={"burden_ids": [fb_bid]}))
            else:
                updated_issues.append(issue)
        issues = updated_issues

        # ── 5. 构建 ClaimIssueMapping ─────────────────────────────────────────
        # Build claim-to-issue mappings; enforce complete coverage
        claim_mappings: list[ClaimIssueMapping] = []
        mapped_claims: set[str] = set()
        for m in llm_output.claim_issue_mapping:
            resolved = [tmp_to_proper.get(tid, tid) for tid in m.issue_tmp_ids if tid]
            if m.claim_id and resolved:
                claim_mappings.append(ClaimIssueMapping(claim_id=m.claim_id, issue_ids=resolved))
                mapped_claims.add(m.claim_id)

        # 强制兜底：未映射的 Claim 映射到第一个 Issue
        # Fallback: unmapped claims default to first issue
        fallback_issue_id = issues[0].issue_id if issues else None
        for c in claims:
            cid = c.get("claim_id", "")
            if cid and cid not in mapped_claims and fallback_issue_id:
                claim_mappings.append(
                    ClaimIssueMapping(claim_id=cid, issue_ids=[fallback_issue_id])
                )

        # ── 6. 构建 DefenseIssueMapping ──────────────────────────────────────
        # Build defense-to-issue mappings; enforce complete coverage
        defense_mappings: list[DefenseIssueMapping] = []
        mapped_defenses: set[str] = set()
        for m in llm_output.defense_issue_mapping:
            resolved = [tmp_to_proper.get(tid, tid) for tid in m.issue_tmp_ids if tid]
            if m.defense_id and resolved:
                defense_mappings.append(
                    DefenseIssueMapping(defense_id=m.defense_id, issue_ids=resolved)
                )
                mapped_defenses.add(m.defense_id)

        # 强制兜底：未映射的 Defense 映射到第一个 Issue
        # Fallback: unmapped defenses default to first issue
        for d in defenses:
            did = d.get("defense_id", "")
            if did and did not in mapped_defenses and fallback_issue_id:
                defense_mappings.append(
                    DefenseIssueMapping(defense_id=did, issue_ids=[fallback_issue_id])
                )

        # ── 7. 组装 IssueTree ─────────────────────────────────────────────────
        return IssueTree(
            case_id=case_id,
            issues=issues,
            burdens=burdens,
            claim_issue_mapping=claim_mappings,
            defense_issue_mapping=defense_mappings,
            extraction_metadata=ExtractionMetadata(
                total_claims_processed=len(claims),
                total_defenses_processed=len(defenses),
                total_evidence_referenced=len(evidence),
                extraction_timestamp=now,
            ).model_dump(),
        )
