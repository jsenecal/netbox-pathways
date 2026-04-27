# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Canonical normalize-toolkit CI/CD shape (5 GHA workflows: ci.yml, publish.yml, docs.yml, release-drafter.yml, pr-title.yml + .github/release-drafter.yml).
- .pre-commit-config.yaml with ruff hooks + standard pre-commit-hooks + a commit-msg stage that rejects AI/Claude attribution lines.
- .git-template/hooks/commit-msg (canonical hook tracked in-tree, referenced by pre-commit).
- CHANGELOG.md (this file).

### Changed

- docs/zensical.toml rewritten to the canonical zensical schema (project / project.theme / [[project.theme.palette]]).
- pyproject.toml: dropped mkdocs from [docs] extra in favor of zensical (matches the toolkit canonical); added extend-exclude for migrations; ignored N806 globally (Django `User = get_user_model()` idiom); added explicit [tool.ruff.format]; added bumpver CHANGELOG.md file pattern; added Documentation URL; added Python 3.14 classifier.

### Removed

- Root-level mkdocs.yml (replaced by docs/zensical.toml).
- SlackLoop model and all of its views, urls, forms, filters, filterforms, tables, serializers, API endpoints, search index entry, navigation menu entry, template_content, ui panel, and pullsheet template block. Slack-loop tracking now lives in netbox-fms whose closure-cable-entry workflow is the right home for it. Migration 0007_cable_routing_redesign no longer creates the SlackLoop model; the slack_loop_location PointField on Structure is unaffected.
