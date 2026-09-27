from pathlib import Path

import pytest

from aurel.config import ConfigError, load_config

TEST_ARTIFACTS = Path(".test_artifacts")


def test_load_default_config_when_no_file_is_present(monkeypatch):
    config_dir = TEST_ARTIFACTS / "default_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(config_dir)

    config = load_config()

    assert config.project_type == "general"
    assert config.audience == "all"
    assert "README.md" in config.community_files
    assert config.file_weights["README.md"] == 25


def test_load_basic_aurel_config():
    config_path = TEST_ARTIFACTS / "aurel.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
project_type: python
audience: students
scoring:
  readme: 40
  contributing: 30
checks:
  readme_paths:
    - docs/CONTRIBUTING.md
  contributing_paths:
    - docs/CONTRIBUTING.md
  require_readme: false
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project_type == "python"
    assert config.audience == "students"
    assert config.signal_paths["readme"] == ("docs/CONTRIBUTING.md",)
    assert config.signal_paths["contributing"] == ("docs/CONTRIBUTING.md",)
    assert config.required_signals["readme"] is False
    assert config.signal_weights["readme"] == 40
    assert config.file_weights["docs/CONTRIBUTING.md"] == 30


def test_load_config_applies_v1_presets_and_custom_labels():
    config_path = TEST_ARTIFACTS / "preset-aurel.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
preset: docs-only
checks:
  beginner_labels:
    - documentation
    - starter task
  required_commands:
    - run
    - build
  command_checks:
    - test
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project_type == "documentation"
    assert config.audience == "docs contributors"
    assert config.required_signals["security"] is False
    assert config.required_signals["code_of_conduct"] is False
    assert config.beginner_labels == ("documentation", "starter task")
    assert config.required_commands == ("run", "build")
    assert config.command_checks == ("test", "run", "build")


def test_load_config_rejects_invalid_scores():
    config_path = TEST_ARTIFACTS / "invalid-aurel.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
scoring:
  readme: not-a-number
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_unknown_keys():
    config_path = TEST_ARTIFACTS / "unknown-aurel.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("surprise: true", encoding="utf-8")

    with pytest.raises(ConfigError, match="Unknown top-level config key"):
        load_config(config_path)


def test_load_config_rejects_non_string_metadata():
    config_path = TEST_ARTIFACTS / "invalid-metadata-aurel.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("project_type: true", encoding="utf-8")

    with pytest.raises(ConfigError, match="'project_type' must be a string"):
        load_config(config_path)


def test_load_config_rejects_non_string_list_items():
    config_path = TEST_ARTIFACTS / "invalid-list-aurel.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
checks:
  beginner_labels:
    - true
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="'checks.beginner_labels' values must be strings"):
        load_config(config_path)


def test_load_config_preserves_hash_inside_quoted_values():
    config_path = TEST_ARTIFACTS / "quoted-label-aurel.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
checks:
  beginner_labels:
    - "#good-first"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.beginner_labels == ("#good-first",)
