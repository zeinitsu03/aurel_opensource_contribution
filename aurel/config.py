"""Configuration loading for Aurel."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SIGNAL_PATHS = {
    "readme": (
        "README.md",
        "README.rst",
        "README",
        ".github/README.md",
        "docs/index.md",
        "docs/README.md",
    ),
    "license": ("LICENSE", "LICENSE.md", "COPYING", "COPYING.md"),
    "contributing": (
        "CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
        "docs/CONTRIBUTING.md",
        "docs/contributing.md",
    ),
    "security": ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md"),
    "code_of_conduct": (
        "CODE_OF_CONDUCT.md",
        ".github/CODE_OF_CONDUCT.md",
        "docs/CODE_OF_CONDUCT.md",
    ),
}

DEFAULT_SIGNAL_LABELS = {
    "readme": "Project overview or docs entry point",
    "license": "License information",
    "contributing": "Contribution guide",
    "security": "Security reporting instructions",
    "code_of_conduct": "Community behavior expectations",
}

DEFAULT_SIGNAL_WEIGHTS = {
    "readme": 25,
    "license": 20,
    "contributing": 20,
    "security": 15,
    "code_of_conduct": 10,
}

DEFAULT_REQUIRED_SIGNALS = {
    "readme": True,
    "license": True,
    "contributing": True,
    "security": True,
    "code_of_conduct": True,
}

DEFAULT_BEGINNER_LABELS = ("good first issue", "help wanted")
DEFAULT_COMMAND_CHECKS = ("install", "run", "test", "lint", "build")
VALID_COMMAND_CHECKS = set(DEFAULT_COMMAND_CHECKS)

PRESETS = {
    "classroom": {
        "audience": "students",
        "required_signals": {
            "readme": True,
            "license": True,
            "contributing": True,
            "security": True,
            "code_of_conduct": True,
        },
        "required_commands": ("install", "run", "test"),
        "beginner_labels": (
            *DEFAULT_BEGINNER_LABELS,
            "first-timers-only",
            "starter task",
        ),
    },
    "maintainer-audit": {
        "audience": "maintainers",
        "required_signals": {
            "readme": True,
            "license": True,
            "contributing": True,
            "security": True,
            "code_of_conduct": True,
        },
        "required_commands": DEFAULT_COMMAND_CHECKS,
        "beginner_labels": DEFAULT_BEGINNER_LABELS,
    },
    "first-timers": {
        "audience": "beginners",
        "required_signals": {
            "readme": True,
            "license": True,
            "contributing": True,
            "security": True,
            "code_of_conduct": True,
        },
        "required_commands": ("install", "run", "test"),
        "beginner_labels": (
            *DEFAULT_BEGINNER_LABELS,
            "first-timers-only",
            "starter task",
        ),
    },
    "docs-only": {
        "project_type": "documentation",
        "audience": "docs contributors",
        "required_signals": {
            "readme": True,
            "license": True,
            "contributing": True,
            "security": False,
            "code_of_conduct": False,
        },
        "required_commands": ("run", "build"),
        "beginner_labels": (
            *DEFAULT_BEGINNER_LABELS,
            "documentation",
            "docs",
        ),
    },
}

VALID_URL_POINTS = 10

DEFAULT_COMMUNITY_FILES = tuple(path for paths in DEFAULT_SIGNAL_PATHS.values() for path in paths)
DEFAULT_FILE_WEIGHTS = {
    path: DEFAULT_SIGNAL_WEIGHTS[signal]
    for signal, paths in DEFAULT_SIGNAL_PATHS.items()
    for path in paths
}


class ConfigError(ValueError):
    """Raised when an Aurel configuration file is invalid."""


@dataclass(frozen=True)
class AurelConfig:
    """Runtime configuration for analysis and scoring."""

    project_type: str = "general"
    audience: str = "all"
    preset: str | None = None
    signal_paths: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: DEFAULT_SIGNAL_PATHS.copy()
    )
    signal_weights: dict[str, int] = field(
        default_factory=lambda: DEFAULT_SIGNAL_WEIGHTS.copy()
    )
    required_signals: dict[str, bool] = field(
        default_factory=lambda: DEFAULT_REQUIRED_SIGNALS.copy()
    )
    documentation_paths: tuple[str, ...] = ("docs/index.md", "docs/README.md")
    beginner_labels: tuple[str, ...] = DEFAULT_BEGINNER_LABELS
    command_checks: tuple[str, ...] = DEFAULT_COMMAND_CHECKS
    required_commands: tuple[str, ...] = ()

    @property
    def community_files(self) -> tuple[str, ...]:
        """Return all configured paths for compatibility with older callers."""

        return tuple(path for paths in self.signal_paths.values() for path in paths)

    @property
    def file_weights(self) -> dict[str, int]:
        """Return path-level weights for compatibility with older callers."""

        return {
            path: self.signal_weights.get(signal, 0)
            for signal, paths in self.signal_paths.items()
            for path in paths
        }


def load_config(path: str | Path | None = None) -> AurelConfig:
    """Load configuration from a basic aurel.yml file.

    The MVP parser intentionally supports a small YAML subset: top-level
    key/value pairs, nested mappings, and nested string lists.
    """

    config_path = Path(path) if path else Path("aurel.yml")
    if not config_path.exists():
        if path:
            raise ConfigError(f"Config file not found: {config_path}")
        return AurelConfig()

    raw_data = _parse_basic_yaml(config_path.read_text(encoding="utf-8"))
    return _build_config(raw_data)


def _build_config(raw_data: dict[str, Any]) -> AurelConfig:
    _reject_unknown_top_level_keys(raw_data)

    preset_name = _optional_string(raw_data.get("preset"), "preset")
    preset = _preset_config(preset_name)

    project_type = _string_value(
        raw_data.get("project_type", preset.get("project_type", "general")),
        "project_type",
    )
    audience = _string_value(
        raw_data.get("audience", preset.get("audience", "all")),
        "audience",
    )

    checks = raw_data.get("checks", {})
    if checks is None:
        checks = {}
    if not isinstance(checks, dict):
        raise ConfigError("The 'checks' section must be a mapping.")

    _reject_unknown_check_keys(checks)

    signal_paths = {key: tuple(paths) for key, paths in DEFAULT_SIGNAL_PATHS.items()}
    documentation_paths = _string_list(
        checks.get("documentation_paths", ("docs/index.md", "docs/README.md")),
        "checks.documentation_paths",
    )

    path_keys = {
        "readme": "readme_paths",
        "license": "license_paths",
        "contributing": "contributing_paths",
        "security": "security_paths",
        "code_of_conduct": "code_of_conduct_paths",
    }
    for signal, config_key in path_keys.items():
        if config_key in checks:
            signal_paths[signal] = _string_list(checks[config_key], f"checks.{config_key}")

    if "community_files" in checks:
        custom_files = _string_list(checks["community_files"], "checks.community_files")
        signal_paths["custom"] = custom_files

    required_signals = DEFAULT_REQUIRED_SIGNALS.copy()
    required_signals.update(preset.get("required_signals", {}))
    required_keys = {
        "readme": "require_readme",
        "license": "require_license",
        "contributing": "require_contributing",
        "security": "require_security",
        "code_of_conduct": "require_code_of_conduct",
    }
    for signal, config_key in required_keys.items():
        if config_key in checks:
            required_signals[signal] = _bool_value(checks[config_key], f"checks.{config_key}")

    beginner_labels = tuple(preset.get("beginner_labels", DEFAULT_BEGINNER_LABELS))
    if "beginner_labels" in checks:
        beginner_labels = _string_list(checks["beginner_labels"], "checks.beginner_labels")

    command_checks = tuple(preset.get("command_checks", DEFAULT_COMMAND_CHECKS))
    if "command_checks" in checks:
        command_checks = _command_list(checks["command_checks"], "checks.command_checks")

    required_commands = tuple(preset.get("required_commands", ()))
    if "required_commands" in checks:
        required_commands = _command_list(
            checks["required_commands"],
            "checks.required_commands",
        )
    command_checks = _merge_unique(command_checks, required_commands)

    signal_weights = DEFAULT_SIGNAL_WEIGHTS.copy()
    scoring = raw_data.get("scoring", {})
    if scoring is None:
        scoring = {}
    if not isinstance(scoring, dict):
        raise ConfigError("The 'scoring' section must be a mapping.")

    for filename, value in scoring.items():
        scoring_key = str(filename)
        signal_key = _scoring_signal_key(scoring_key, signal_paths)
        if signal_key is None:
            raise ConfigError(
                f"Unknown scoring key {scoring_key!r}. Use a configured signal "
                "name or one of its configured paths."
            )
        try:
            points = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Score for {filename!r} must be an integer.") from exc
        if points < 0:
            raise ConfigError(f"Score for {filename!r} cannot be negative.")
        if points > 100:
            raise ConfigError(f"Score for {filename!r} cannot be greater than 100.")
        signal_weights[signal_key] = points

    return AurelConfig(
        project_type=project_type,
        audience=audience,
        preset=preset_name,
        signal_paths=signal_paths,
        signal_weights=signal_weights,
        required_signals=required_signals,
        documentation_paths=documentation_paths,
        beginner_labels=beginner_labels,
        command_checks=command_checks,
        required_commands=required_commands,
    )


def _reject_unknown_top_level_keys(raw_data: dict[str, Any]) -> None:
    allowed = {"project_type", "audience", "preset", "scoring", "checks"}
    unknown = sorted(set(raw_data) - allowed)
    if unknown:
        raise ConfigError(f"Unknown top-level config key: {unknown[0]}")


def _reject_unknown_check_keys(checks: dict[str, Any]) -> None:
    allowed = {
        "readme_paths",
        "license_paths",
        "contributing_paths",
        "security_paths",
        "code_of_conduct_paths",
        "documentation_paths",
        "community_files",
        "require_readme",
        "require_license",
        "require_contributing",
        "require_security",
        "require_code_of_conduct",
        "beginner_labels",
        "command_checks",
        "required_commands",
    }
    unknown = sorted(set(checks) - allowed)
    if unknown:
        raise ConfigError(f"Unknown checks config key: {unknown[0]}")


def _preset_config(preset_name: str | None) -> dict[str, Any]:
    if preset_name is None:
        return {}
    if preset_name not in PRESETS:
        valid = ", ".join(sorted(PRESETS))
        raise ConfigError(f"Unknown preset {preset_name!r}. Valid presets: {valid}.")
    return PRESETS[preset_name]


def _optional_string(value: Any, key: str) -> str | None:
    if value is None:
        return None
    return _string_value(value, key)


def _string_value(value: Any, key: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"'{key}' must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ConfigError(f"'{key}' cannot be empty.")
    return normalized


def _string_list(value: Any, key: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ConfigError(f"'{key}' must be a list.")
    invalid_items = [item for item in value if not isinstance(item, str)]
    if invalid_items:
        raise ConfigError(f"'{key}' values must be strings.")
    normalized = tuple(item.strip() for item in value)
    if not normalized:
        raise ConfigError(f"'{key}' must include at least one path.")
    if any(not item for item in normalized):
        raise ConfigError(f"'{key}' cannot contain empty values.")
    return normalized


def _command_list(value: Any, key: str) -> tuple[str, ...]:
    commands = _string_list(value, key)
    invalid = [command for command in commands if command not in VALID_COMMAND_CHECKS]
    if invalid:
        valid = ", ".join(DEFAULT_COMMAND_CHECKS)
        raise ConfigError(f"'{key}' contains invalid command {invalid[0]!r}. Use: {valid}.")
    return commands


def _merge_unique(primary: tuple[str, ...], extra: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for item in (*primary, *extra):
        if item not in merged:
            merged.append(item)
    return tuple(merged)


def _scoring_signal_key(key: str, signal_paths: dict[str, tuple[str, ...]]) -> str | None:
    if key in signal_paths:
        return key
    for signal, paths in signal_paths.items():
        if key in paths:
            return signal
    return None


def _bool_value(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ConfigError(f"'{key}' must be true or false.")


def _parse_basic_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_section: str | None = None
    current_list_key: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_inline_comment(raw_line)
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            key, value = _split_key_value(stripped, line_number)
            current_section = key if value == "" else None
            current_list_key = None
            data[key] = {} if value == "" else _coerce_scalar(value)
            continue

        if current_section is None:
            raise ConfigError(f"Unexpected indentation on line {line_number}.")

        section = data[current_section]
        if not isinstance(section, dict):
            raise ConfigError(f"Section {current_section!r} must be a mapping.")

        if indent == 2:
            key, value = _split_key_value(stripped, line_number)
            if value == "":
                section[key] = []
                current_list_key = key
            else:
                section[key] = _coerce_scalar(value)
                current_list_key = None
            continue

        if indent == 4 and current_list_key and stripped.startswith("- "):
            section[current_list_key].append(_coerce_scalar(stripped[2:].strip()))
            continue

        raise ConfigError(f"Unsupported YAML structure on line {line_number}.")

    return data


def _strip_inline_comment(line: str) -> str:
    quote_char: str | None = None
    escaped = False

    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote_char == character:
                quote_char = None
            elif quote_char is None:
                quote_char = character
            continue
        if character == "#" and quote_char is None:
            return line[:index].rstrip()

    return line.rstrip()


def _split_key_value(line: str, line_number: int) -> tuple[str, str]:
    if ":" not in line:
        raise ConfigError(f"Expected key/value pair on line {line_number}.")
    key, value = line.split(":", 1)
    key = key.strip()
    if not key:
        raise ConfigError(f"Missing key on line {line_number}.")
    return key, value.strip()


def _coerce_scalar(value: str) -> str | int | bool:
    normalized = value.strip()
    if (
        len(normalized) >= 2
        and normalized[0] in {"'", '"'}
        and normalized[-1] == normalized[0]
    ):
        return normalized[1:-1]
    if normalized.lower() == "true":
        return True
    if normalized.lower() == "false":
        return False
    try:
        return int(normalized)
    except ValueError:
        return normalized
