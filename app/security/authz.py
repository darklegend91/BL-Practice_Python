"""Authorization rules enforced in service functions, not only HTTP routes.

Worker and import paths call the same checks, so no code path can bypass them
(guide section 11). Platform catalog roles are deliberately separate from
workspace roles: a customer workspace owner cannot publish shared catalog prices.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass


class WorkspaceRole(str, enum.Enum):
    OWNER = "owner"
    ANALYST = "analyst"
    VIEWER = "viewer"


class PlatformRole(str, enum.Enum):
    NONE = "none"
    CATALOG_EDITOR = "catalog_editor"
    CATALOG_REVIEWER = "catalog_reviewer"
    CATALOG_ADMIN = "catalog_admin"


class NotAuthenticated(Exception):
    pass


class Forbidden(Exception):
    def __init__(self, action: str) -> None:
        super().__init__(f"not permitted: {action}")
        self.action = action


@dataclass(frozen=True)
class Principal:
    """The verified caller. Constructed only from a validated session."""

    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    workspace_role: WorkspaceRole | None
    platform_role: PlatformRole

    # --- workspace ---------------------------------------------------------
    def require_member(self) -> uuid.UUID:
        if self.organization_id is None or self.workspace_role is None:
            raise Forbidden("workspace membership required")
        return self.organization_id

    def require_analyst(self) -> uuid.UUID:
        organization_id = self.require_member()
        if self.workspace_role not in (WorkspaceRole.OWNER, WorkspaceRole.ANALYST):
            raise Forbidden("analyst role required")
        return organization_id

    def require_owner(self) -> uuid.UUID:
        organization_id = self.require_member()
        if self.workspace_role is not WorkspaceRole.OWNER:
            raise Forbidden("workspace owner role required")
        return organization_id

    # --- platform catalog --------------------------------------------------
    def require_catalog_editor(self) -> None:
        if self.platform_role not in (
            PlatformRole.CATALOG_EDITOR,
            PlatformRole.CATALOG_REVIEWER,
            PlatformRole.CATALOG_ADMIN,
        ):
            raise Forbidden("catalog editor role required")

    def require_catalog_reviewer(self) -> None:
        if self.platform_role not in (
            PlatformRole.CATALOG_REVIEWER,
            PlatformRole.CATALOG_ADMIN,
        ):
            raise Forbidden("catalog reviewer role required")

    def require_catalog_admin(self) -> None:
        if self.platform_role is not PlatformRole.CATALOG_ADMIN:
            raise Forbidden("catalog administrator role required")


class SelfApprovalRefused(Forbidden):
    """An editor may not approve their own critical change."""

    def __init__(self) -> None:
        super().__init__(
            "a revision must be approved by someone other than its author"
        )


def check_independent_review(author_id: uuid.UUID, reviewer_id: uuid.UUID) -> None:
    if author_id == reviewer_id:
        raise SelfApprovalRefused()
