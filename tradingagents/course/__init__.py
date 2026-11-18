"""Course extension package (F1-F5). See ``architecture-blueprint.md`` and ADR-001.

Leaf modules live in subpackages and must not import each other directly;
cross-module data flows through JSON-serializable contracts.
"""
