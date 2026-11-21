"""Course extension leaf packages for the CS5351 TradingAgents project.

Each leaf package (evidence, budget, safety, data_quality, audit) is owned by a
separate role and must not import another leaf package directly; collaboration is
by shared JSON contracts or a thin orchestrator (NFR-005, ADR-001). This package
marker deliberately defines no imports so adding one leaf never forces another
leaf's dependencies to load.
"""
