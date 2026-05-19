from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

EntryType = Literal["file", "directory"]
LimitKind = Literal[
    "not-directly-observable",
    "permission-denied",
    "scan-error",
    "skipped-symlink",
    "truncated-limitations",
    "unavailable-target",
]


@dataclass(frozen=True)
class ScanTarget:
    name: str
    path: str
    description: str


@dataclass(frozen=True)
class ScanOptions:
    top_directories: int = 10
    top_files: int = 20
    minimum_report_size_bytes: int = 50 * 1024 * 1024
    stale_threshold_days: int = 365


@dataclass(frozen=True)
class ObservationLimit:
    kind: LimitKind
    path: str
    message: str


@dataclass(frozen=True)
class ObservedEntry:
    path: str
    size_bytes: int
    entry_type: EntryType
    target_name: str
    is_partial: bool = False
    last_modified_at: float | None = None


@dataclass(frozen=True)
class ClassifiedFinding:
    path: str
    size_bytes: int
    entry_type: EntryType
    target_name: str
    is_partial: bool
    category: str
    category_label: str
    review_guidance: str
    rule_id: str
    explanation: str
    last_modified_at: float | None = None


@dataclass(frozen=True)
class CategorySummary:
    category: str
    category_label: str
    review_guidance: str
    total_size_bytes: int
    item_count: int


@dataclass
class ScanSnapshot:
    included_targets: list[ScanTarget] = field(default_factory=list)
    entries: list[ObservedEntry] = field(default_factory=list)
    unknown_entries: list[ObservedEntry] = field(default_factory=list)
    total_observed_bytes: int = 0
    category_totals: dict[tuple[str, str, str], dict[str, int]] = field(default_factory=dict)
    directory_sizes: dict[str, int] = field(default_factory=dict)
    directory_targets: dict[str, str] = field(default_factory=dict)
    directory_newest_mtime: dict[str, float] = field(default_factory=dict)
    partial_directories: set[str] = field(default_factory=set)
    omitted_limitations: int = 0
    limitations: list[ObservationLimit] = field(default_factory=list)


@dataclass
class ScanReport:
    generated_at: str
    included_targets: list[ScanTarget]
    options: ScanOptions
    total_observed_bytes: int
    category_summaries: list[CategorySummary]
    top_directories: list[ClassifiedFinding]
    top_files: list[ClassifiedFinding]
    unknown_large_items: list[ClassifiedFinding]
    limitations: list[ObservationLimit]
    stale_large_items: list[ClassifiedFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
