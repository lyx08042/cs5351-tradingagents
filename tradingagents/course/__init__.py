"""Course extension package (F1-F5). See ``architecture-blueprint.md`` and ADR-001.

This package only holds the course leaf modules. The audit leaf lives in
``tradingagents.course.audit``. Importing this package must not pull in other
leaf modules, so this stays a side-effect-free package marker.
"""
