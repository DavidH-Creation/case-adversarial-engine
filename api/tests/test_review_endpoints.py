"""Tests for Phase 3: human review endpoints."""

import pytest


class TestSubmitReview:
    def test_submit_review_pending(self, client, analyzed_case_id):
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "pending_review"
        assert body["case_id"] == analyzed_case_id
        assert "review_id" in body

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
        # Verify case detail reflects review_status
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
            json={
                "action": "revision_requested",
                "comment": "需要补充分析",
                "section_flags": [
                    {
                        "section_key": "issue.issue-001",
                        "flag": "needs_revision",
                        "comment": "论证不充分",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "revision_requested"
        assert len(body["section_flags"]) == 1

    def test_resubmit_after_revision_requested(self, client, analyzed_case_id):
        # pending_review → revision_requested → pending_review again
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "revision_requested"},
        )
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 200


class TestReviewStateMachine:
    def test_cannot_review_unanalyzed_case(self, client, created_case_id):
        resp = client.post(
            f"/api/cases/{created_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 400

    def test_cannot_approve_without_pending(self, client, analyzed_case_id):
        """Cannot approve a case that hasn't been submitted for review."""
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "approved"},
        )
        assert resp.status_code == 400

    def test_cannot_submit_after_approved(self, client, analyzed_case_id):
        """approved is a terminal state."""
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

    def test_cannot_submit_after_rejected(self, client, analyzed_case_id):
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
            json={"action": "pending_review"},
        )
        assert resp.status_code == 400

    def test_invalid_action_value(self, client, analyzed_case_id):
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "none"},
        )
        assert resp.status_code == 400


class TestReviewList:
    def test_list_reviews_empty(self, client, analyzed_case_id):
        resp = client.get(f"/api/cases/{analyzed_case_id}/reviews")
        assert resp.status_code == 200
        body = resp.json()
        assert body["case_id"] == analyzed_case_id
        assert body["current_review_status"] == "none"
        assert body["reviews"] == []

    def test_list_reviews_after_submit(self, client, analyzed_case_id):
        client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        resp = client.get(f"/api/cases/{analyzed_case_id}/reviews")
        body = resp.json()
        assert body["current_review_status"] == "pending_review"
        assert len(body["reviews"]) == 1

    def test_get_single_review(self, client, analyzed_case_id):
        submit = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        review_id = submit.json()["review_id"]
        resp = client.get(
            f"/api/cases/{analyzed_case_id}/reviews/{review_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["review_id"] == review_id

    def test_get_nonexistent_review(self, client, analyzed_case_id):
        resp = client.get(
            f"/api/cases/{analyzed_case_id}/reviews/rev-nonexistent"
        )
        assert resp.status_code == 404


class TestCaseListReviewStatus:
    def test_case_list_includes_review_status(self, client, analyzed_case_id):
        resp = client.get("/api/cases")
        assert resp.status_code == 200
        items = resp.json()["items"]
        match = [i for i in items if i["case_id"] == analyzed_case_id]
        assert len(match) == 1
        assert match[0]["review_status"] == "none"


class TestReviewPersistence:
    def test_review_persisted_to_disk(self, client, analyzed_case_id):
        """Review records should be persisted to disk."""
        resp = client.post(
            f"/api/cases/{analyzed_case_id}/reviews",
            json={"action": "pending_review"},
        )
        assert resp.status_code == 200
        review_id = resp.json()["review_id"]
        # Verify the review file exists on disk
        from api.service import _WORKSPACE_BASE

        reviews_dir = _WORKSPACE_BASE / analyzed_case_id / "reviews"
        assert (reviews_dir / f"{review_id}.json").exists()
