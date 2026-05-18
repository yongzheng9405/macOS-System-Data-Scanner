from __future__ import annotations

from dataclasses import dataclass

from macos_system_data_scanner.models import ClassifiedFinding, ObservedEntry


@dataclass(frozen=True)
class ClassificationRule:
    rule_id: str
    category: str
    category_label: str
    review_guidance: str
    explanation: str
    markers: tuple[str, ...]


RULES: tuple[ClassificationRule, ...] = (
    ClassificationRule(
        rule_id="device-backups",
        category="device-backups",
        category_label="Device backups",
        review_guidance="needs-care",
        explanation="MobileSync backups can be large and may still be needed for device restores.",
        markers=("/library/application support/mobilesync/backup",),
    ),
    ClassificationRule(
        rule_id="xcode-data",
        category="developer-tooling",
        category_label="Developer tooling",
        review_guidance="safe-review",
        explanation="Xcode archives, simulators, or build artifacts are common large developer files.",
        markers=(
            "/library/developer/xcode/deriveddata",
            "/library/developer/xcode/archives",
            "/library/developer/coresimulator",
            "/library/developer/xcode/ios devicesupport",
        ),
    ),
    ClassificationRule(
        rule_id="virtualization-data",
        category="virtual-machines",
        category_label="Virtual machines and containers",
        review_guidance="needs-care",
        explanation="Docker or virtual machine data can be large but may be in active use.",
        markers=(
            "/.docker",
            "/library/containers/com.docker.docker",
            "/library/group containers/group.com.docker",
            "/parallels",
            "/vmware",
        ),
    ),
    ClassificationRule(
        rule_id="messages-mail",
        category="communication-attachments",
        category_label="Mail and message data",
        review_guidance="needs-care",
        explanation="Mail and Messages data may include attachments or message history you still need.",
        markers=("/library/messages", "/library/mail"),
    ),
    ClassificationRule(
        rule_id="caches",
        category="caches",
        category_label="Caches",
        review_guidance="safe-review",
        explanation="Caches are commonly reviewed first because they are often regenerable.",
        markers=("/library/caches",),
    ),
    ClassificationRule(
        rule_id="logs",
        category="logs",
        category_label="Logs",
        review_guidance="safe-review",
        explanation="Log directories may grow over time and are often reasonable to inspect.",
        markers=("/library/logs", "/private/var/log"),
    ),
    ClassificationRule(
        rule_id="containers",
        category="application-support",
        category_label="Application support data",
        review_guidance="needs-care",
        explanation="Application containers often hold app state and should be reviewed carefully.",
        markers=("/library/containers", "/library/group containers"),
    ),
    ClassificationRule(
        rule_id="application-support",
        category="application-support",
        category_label="Application support data",
        review_guidance="needs-care",
        explanation="Application support directories often contain active app data and indexes.",
        markers=("/library/application support",),
    ),
    ClassificationRule(
        rule_id="developer-data",
        category="developer-tooling",
        category_label="Developer tooling",
        review_guidance="safe-review",
        explanation="Developer tooling directories often hold SDKs, simulators, or temporary artifacts.",
        markers=("/library/developer",),
    ),
)


def classify_entry(entry: ObservedEntry) -> ClassifiedFinding:
    normalized_path = entry.path.lower()
    for rule in RULES:
        if any(_path_matches(normalized_path, marker) for marker in rule.markers):
            return ClassifiedFinding(
                path=entry.path,
                size_bytes=entry.size_bytes,
                entry_type=entry.entry_type,
                target_name=entry.target_name,
                is_partial=entry.is_partial,
                category=rule.category,
                category_label=rule.category_label,
                review_guidance=rule.review_guidance,
                rule_id=rule.rule_id,
                explanation=rule.explanation,
            )

    return ClassifiedFinding(
        path=entry.path,
        size_bytes=entry.size_bytes,
        entry_type=entry.entry_type,
        target_name=entry.target_name,
        is_partial=entry.is_partial,
        category="unknown",
        category_label="Unknown large items",
        review_guidance="needs-care",
        rule_id="unknown",
        explanation="This path did not match any known classification rule and needs manual review.",
    )


def _path_matches(normalized_path: str, marker: str) -> bool:
    return (
        normalized_path == marker
        or normalized_path.endswith(marker)
        or normalized_path.startswith(f"{marker}/")
        or f"{marker}/" in normalized_path
    )
