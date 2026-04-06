"""Tests for Phase 3: human review workflow endpoints."""

import pytest


class TestSubmitReview:
    """POST /api/cases/{case_id}/reviews"""

    def test_submit_pending_review(self, client, analyzed_case_id):
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "pending_review"
        assert data["case_id"] == analyzed_case_id
        assert "review_id" in data
        assert data["reviewer_id"] == "anonymous"

    def test_approve_case(self, client, analyzed_case_id):
        # First submit for review
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        # Then approve
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "approved", "comment": "LGTM"},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "approved"
        assert resp.json()["comment"] == "LGTM"

        # CaseInfoResponse should reflect approved status
        detail = client.get(f"/api/cases/{analyzed_case_id}")
        assert detail.json()["review_status"] == "approved"

    def test_reject_case(self, client, analyzed_case_id):
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "rejected", "comment": "证据不足"},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "rejected"

    def test_revision_requested(self, client, analyzed_case_id):
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "revision_requested", "comment": "需要补充论证"},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "revision_requested"

        # After revision_requested, can submit pending_review again
        resp2 = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp2.status_code == 200

    def test_section_flags_persisted(self, client, analyzed_case_id):
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        flags = [
            {"section_key": "issue.issue-001", "flag": "approved"},
            {
                "section_key": "evidence.ev-003",
                "flag": "flagged",
                "comment": "证据真实性存疑",
            },
        ]
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "approved", "section_flags": flags},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["section_flags"]) == 2
        assert data["section_flags"][0]["section_key"] == "issue.issue-001"

    def test_cannot_review_unanalyzed_case(self, client, created_case_id):
        resp = client.post(
            f"/api/cases/{created_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 400

    def test_approved_is_terminal(self, client, analyzed_case_id):
        """approved is a terminal state — no further reviews allowed."""
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "approved"},
        )
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 400

    def test_rejected_is_terminal(self, client, analyzed_case_id):
        """rejected is a terminal state."""
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "rejected"},
        )
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "approved"},
        )
        assert resp.status_code == 400

    def test_cannot_approve_without_pending(self, client, analyzed_case_id):
        """Cannot approve when review_status is still 'none'."""
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "approved"},
        )
        assert resp.status_code == 400

    def test_action_none_rejected(self, client, analyzed_case_id):
        """action=none is not a valid submission action."""
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "none"},
        )
        assert resp.status_code == 400

    def test_nonexistent_case_404(self, client):
        resp = client.post(
            "/api/cases/case-nonexistent/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 404


class TestListReviews:
    """GET /api/cases/{case_id}/reviews"""

    def test_empty_review_list(self, client, analyzed_case_id):
        resp = client.get(f"/api/cases/{analyzed_case_id}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == analyzed_case_id
        assert data["current_review_status"] == "none"
        assert data["reviews"] == []

    def test_review_list_after_submissions(self, client, analyzed_case_id):
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "approved", "comment": "OK"},
        )
        resp = client.get(f"/api/cases/{analyzed_case_id}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_review_status"] == "approved"
        assert len(data["reviews"]) == 2

    def test_review_list_nonexistent_case(self, client):
        resp = client.get("/api/cases/case-nonexistent/reviews")
        assert resp.status_code == 404


class TestCaseListReviewStatus:
    """CaseListEntry should include review_status."""

    def test_case_list_includes_review_status(self, client, analyzed_case_id):
        resp = client.get("/api/cases")
        assert resp.status_code == 200
        items = resp.json()["items"]
        entry = next(e for e in items if e["case_id"] == analyzed_case_id)
        assert entry["review_status"] == "none"

        # Submit pending review
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        resp2 = client.get("/api/cases")
        items2 = resp2.json()["items"]
        entry2 = next(e for e in items2 if e["case_id"] == analyzed_case_id)
        assert entry2["review_status"] == "pending_review"
