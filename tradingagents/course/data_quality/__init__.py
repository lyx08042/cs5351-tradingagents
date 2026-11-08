"""F4 data sufficiency: classify data domains and gate downstream decisions.

INV-004: unavailable/unknown data must never be treated as neutral; unknown
defaults to denial (default-deny unknown).

This package only produces traceable, JSON-serializable events. Persistence of
those events is module E's responsibility (NFR-004).
"""
