"""
Action enum + role-based permission matrix + require_permission() dependency.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable

from fastapi import Depends, HTTPException

from .users import UserRole


class Action(str, Enum):
    case_create = "case_create"
    case_view = "case_view"
    case_list = "case_list"
    material_add = "material_add"
    extraction_trigger = "extraction_trigger"
    analysis_trigger = "analysis_trigger"
    review_submit = "review_submit"
    review_decide = "review_decide"
    export_case = "export_case"
    admin_users = "admin_users"


PERMISSIONS: dict[UserRole, set[Action]] = {
    UserRole.admin: set(Action),
    UserRole.senior_lawyer: {
        Action.case_create, Action.case_view, Action.case_list,
        Action.material_add, Action.extraction_trigger,
        Action.analysis_trigger, Action.review_submit, Action.export_case,
    },
    UserRole.junior_lawyer: {
        Action.case_create, Action.case_view, Action.case_list,
        Action.material_add, Action.extraction_trigger,
    },
    UserRole.reviewer: {
        Action.case_view, Action.case_list,
        Action.review_decide, Action.export_case,
    },
    UserRole.readonly: {
        Action.case_view, Action.case_list,
    },
}


def require_permission(action: Action) -> Callable:
    """FastAPI dependency factory: inject UserContext, check role permission.

    Usage::

        @app.post("/api/cases/")
        async def create_case(
            body: CreateCaseRequest,
            user: UserContext = Depends(require_permission(Action.case_create)),
        ): ...
    """
    from .auth import UserContext, get_current_user

    def _check(user: UserContext = Depends(get_current_user)) -> UserContext:
        if action not in PERMISSIONS.get(user.role, set()):
            raise HTTPException(status_code=403, detail=f"权限不足: {action.value}")
        return user

    return _check
