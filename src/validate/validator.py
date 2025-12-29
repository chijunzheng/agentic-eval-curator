"""MCQ item validator with configurable rules."""

from dataclasses import dataclass, field

from src.models import CDRChunk, MCQItem, ValidationResult
from src.validate.rules import Rule, get_default_rules


@dataclass
class ValidationReport:
    """Aggregated validation results for a batch of items."""

    total_items: int = 0
    passed_items: int = 0
    failed_items: int = 0
    results: list[ValidationResult] = field(default_factory=list)
    failure_counts: dict[str, int] = field(default_factory=dict)
    warning_counts: dict[str, int] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Calculate the pass rate as a percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.passed_items / self.total_items) * 100

    def get_failed_qids(self) -> list[str]:
        """Return list of QIDs that failed validation."""
        return [r.qid for r in self.results if not r.passed]

    def get_passed_qids(self) -> list[str]:
        """Return list of QIDs that passed validation."""
        return [r.qid for r in self.results if r.passed]

    def to_dict(self) -> dict:
        """Convert report to dictionary for serialization."""
        return {
            "total_items": self.total_items,
            "passed_items": self.passed_items,
            "failed_items": self.failed_items,
            "pass_rate": self.pass_rate,
            "failure_counts": self.failure_counts,
            "warning_counts": self.warning_counts,
            "failed_qids": self.get_failed_qids(),
        }


class Validator:
    """Validates MCQ items against a configurable set of rules."""

    def __init__(self, rules: list[Rule] | None = None):
        """
        Initialize the validator.

        Args:
            rules: List of Rule instances to apply. If None, uses default rules.
        """
        self.rules = rules if rules is not None else get_default_rules()

    def validate(
        self, item: MCQItem, chunks: dict[str, CDRChunk]
    ) -> ValidationResult:
        """
        Validate a single MCQ item against all configured rules.

        Args:
            item: The MCQ item to validate.
            chunks: Dictionary mapping chunk_id to CDRChunk for evidence verification.

        Returns:
            ValidationResult with pass/fail status and any failed rules or warnings.
        """
        failed_rules = []
        warnings = []

        for rule in self.rules:
            try:
                passed, message = rule.validate(item, chunks)
                if not passed:
                    failed_rules.append(f"{rule.name}: {message}")
            except Exception as e:
                # Rule execution error - treat as failure
                failed_rules.append(f"{rule.name}: Rule error - {e!s}")

        return ValidationResult(
            qid=item.qid,
            passed=len(failed_rules) == 0,
            failed_rules=failed_rules,
            warnings=warnings,
        )

    def validate_batch(
        self,
        items: list[MCQItem],
        chunks: dict[str, CDRChunk],
    ) -> ValidationReport:
        """
        Validate a batch of MCQ items.

        Args:
            items: List of MCQ items to validate.
            chunks: Dictionary mapping chunk_id to CDRChunk for evidence verification.

        Returns:
            ValidationReport with aggregated results.
        """
        report = ValidationReport(total_items=len(items))

        for item in items:
            result = self.validate(item, chunks)
            report.results.append(result)

            if result.passed:
                report.passed_items += 1
            else:
                report.failed_items += 1

                # Count failures by rule
                for failed_rule in result.failed_rules:
                    # Extract rule name (before the colon)
                    rule_name = failed_rule.split(":")[0].strip()
                    report.failure_counts[rule_name] = (
                        report.failure_counts.get(rule_name, 0) + 1
                    )

            # Count warnings
            for warning in result.warnings:
                warning_type = warning.split(":")[0].strip()
                report.warning_counts[warning_type] = (
                    report.warning_counts.get(warning_type, 0) + 1
                )

        return report

    def add_rule(self, rule: Rule) -> None:
        """Add a validation rule to the validator."""
        self.rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a rule by name.

        Args:
            rule_name: Name of the rule to remove.

        Returns:
            True if rule was found and removed, False otherwise.
        """
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                self.rules.pop(i)
                return True
        return False

    def get_rule_names(self) -> list[str]:
        """Return list of active rule names."""
        return [rule.name for rule in self.rules]
