"""Raw domain observation -> available | unavailable | unknown.

Anchors: FR-004, INV-004, ADR-001. Classification is deterministic and never
raises on bad raw input; anything uncertain becomes ``unknown`` so that
downstream admission defaults to denial (default-deny unknown).

Explicit neutral: a valid observation whose sentiment is exactly 0 is still
``available`` (neutral is a data semantic, not an availability state).
"""

from __future__ import annotations

from .contracts import ContractError, DomainLabel, RawObservation, parse_iso_date


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def classify(observation: RawObservation) -> DomainLabel:
    """Classify a single raw observation into a domain status label (FR-004).

    Resolution order (deterministic, fail-closed):

    1. ``probe_error`` set -> ``unknown`` (probe inconclusive).
    2. ``kind == "no_data"`` with a valid source -> ``unavailable``.
    3. ``kind == "value"`` needing ``value_present`` + valid source + valid date
       -> ``available``; otherwise ``unknown`` (never filled in as 0/neutral).
    4. Anything else (``kind == "missing"`` or unknown kinds) -> ``unknown``.
    """
    domain = observation.domain
    as_of = observation.observed_as_of if observation.observed_as_of is not None else ""

    # 1. Inconclusive probe -> unknown regardless of other fields.
    if observation.probe_error:
        return DomainLabel(
            domain=domain,
            status="unknown",
            as_of=as_of,
            reason=f"probe_error: {observation.probe_error}",
            source=observation.source,
            sentiment=None,
        )

    # 2. Source explicitly reported no data for the date.
    if observation.kind == "no_data":
        if not observation.source_valid():
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="no_data without a valid source; cannot confirm unavailability",
                source=observation.source,
            )
        return DomainLabel(
            domain=domain,
            status="unavailable",
            as_of=as_of,
            reason="source reported no data for the analysis window",
            source=observation.source,
            sentiment=None,
        )

    # 3. A real value observation.
    if observation.kind == "value":
        if not observation.value_present or observation.value is None:
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="value field missing; refusing to default to 0/neutral",
                source=observation.source,
            )
        if not observation.source_valid():
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="value present but source is missing/invalid",
                source=observation.source,
            )
        try:
            parse_iso_date(observation.observed_as_of)
        except ContractError as exc:
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason=f"observation date undeterminable: {exc}",
                source=observation.source,
            )
        if (
            observation.sentiment is not None
            and not _is_number(observation.sentiment)
        ):
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="sentiment present but not numeric",
                source=observation.source,
            )
        sentiment = observation.sentiment
        if sentiment is not None and float(sentiment) == 0.0:
            reason = "explicit neutral (sentiment == 0) from valid source data"
        else:
            reason = "valid source data present for the analysis window"
        return DomainLabel(
            domain=domain,
            status="available",
            as_of=as_of,
            reason=reason,
            source=observation.source,
            sentiment=sentiment,
        )

    # 4. Missing field / unknown kind.
    reason = (
        "field absent; refusing to default to 0/neutral"
        if observation.kind == "missing"
        else f"unknown observation kind {observation.kind!r}"
    )
    return DomainLabel(
        domain=domain,
        status="unknown",
        as_of=as_of,
        reason=reason,
        source=observation.source,
    )


__all__ = ["classify"]
