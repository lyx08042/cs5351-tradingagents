"""Course extension package (F1-F5). See ``architecture-blueprint.md`` and ADR-001.

Leaf modules live in ``tradingagents.course.{audit,budget,data_quality,evidence,safety}``.
Each subpackage is owned by one role and must not import another leaf module; shared
contracts travel through plain data, not through imports. Importing this package must
not pull in other leaf modules, so this stays a side-effect-free package marker.
"""

__all__: list[str] = []
