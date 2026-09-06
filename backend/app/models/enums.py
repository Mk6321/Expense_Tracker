from enum import Enum


class StrEnum(str, Enum):
    """Python 3.10 target -- enum.StrEnum only landed in 3.11."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class MemberRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class MemberStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class SplitType(StrEnum):
    EQUAL = "equal"
    EXACT = "exact"
    PERCENTAGE = "percentage"
    SHARES = "shares"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    REVERSE = "reverse"
    ROLE_CHANGE = "role_change"
    MEMBER_ADD = "member_add"
    MEMBER_REMOVE = "member_remove"
    GROUP_ARCHIVE = "group_archive"
