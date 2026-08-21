from __future__ import annotations

from copy import deepcopy

import pytest

from rigmanifest.catalog_io import catalog_with_user_records
from rigmanifest.models import (
    FrequencyCatalog,
    PowerIntentMode,
    PowerTier,
    SignalingKind,
)


def _definition() -> dict[str, object]:
    return {
        "id": "user-frequency",
        "name": "User frequency",
        "origin": "user",
        "read_only": False,
        "receive_frequency_hz": 146_520_000,
        "transmit_behavior": "same",
        "transmit_frequency_hz": None,
        "offset_hz": None,
        "mode": "FM",
        "tone": {"mode": "none"},
        "tags": [],
        "priority": "normal",
        "notes": "",
    }


def _set() -> dict[str, object]:
    return {
        "id": "user-set",
        "name": "User set",
        "origin": "user",
        "read_only": False,
        "description": "",
        "members": [
            {
                "frequency_definition_id": "user-frequency",
                "position": 0,
                "channel_designator": None,
            }
        ],
    }


@pytest.mark.parametrize(
    ("tone", "tx_kind", "rx_kind", "tx_polarity", "rx_polarity"),
    [
        ({"mode": "none"}, SignalingKind.NONE, SignalingKind.NONE, "N", "N"),
        (
            {"mode": "tone", "encode_hz": 100},
            SignalingKind.CTCSS,
            SignalingKind.NONE,
            "N",
            "N",
        ),
        (
            {"mode": "tsql", "encode_hz": 100, "decode_hz": 123},
            SignalingKind.CTCSS,
            SignalingKind.CTCSS,
            "N",
            "N",
        ),
        (
            {"mode": "dtcs", "dtcs_code": 23, "dtcs_polarity": "NR"},
            SignalingKind.DCS,
            SignalingKind.DCS,
            "N",
            "R",
        ),
    ],
)
def test_all_legacy_tone_shapes_migrate(
    tone: dict[str, object],
    tx_kind: SignalingKind,
    rx_kind: SignalingKind,
    tx_polarity: str,
    rx_polarity: str,
) -> None:
    record = _definition()
    record["tone"] = tone

    catalog = catalog_with_user_records(FrequencyCatalog((), ()), [record], [_set()])

    definition = catalog.definitions[0]
    assert definition.transmit_access.kind is tx_kind
    assert definition.receive_squelch.kind is rx_kind
    assert definition.transmit_access.dcs_polarity == tx_polarity
    assert definition.receive_squelch.dcs_polarity == rx_polarity


def test_explicit_signaling_takes_precedence_over_legacy_tone() -> None:
    record = _definition()
    record["transmit_access"] = {
        "kind": "ctcss",
        "ctcss_hz": 100,
        "dcs_code": None,
        "dcs_polarity": "N",
    }
    record["receive_squelch"] = {
        "kind": "dcs",
        "ctcss_hz": None,
        "dcs_code": 23,
        "dcs_polarity": "R",
    }

    catalog = catalog_with_user_records(FrequencyCatalog((), ()), [record], [_set()])

    assert catalog.definitions[0].receive_squelch.dcs_polarity == "R"


def test_structured_and_legacy_power_intent_are_parsed() -> None:
    relative = _definition()
    relative["power_intent"] = {
        "mode": "relative",
        "tier": "high",
        "nominal_dbm": None,
        "imported_driver_reference": "Example_Radio",
        "imported_label": "HI",
        "imported_dbm": 36.99,
    }
    parsed = catalog_with_user_records(
        FrequencyCatalog((), ()),
        [relative],
        [_set()],
    ).definitions[0]
    assert parsed.power_intent.mode is PowerIntentMode.RELATIVE
    assert parsed.power_intent.tier is PowerTier.HIGH

    nominal = _definition()
    nominal["power_dbm"] = 36.99
    nominal["power_label"] = "High"
    parsed = catalog_with_user_records(
        FrequencyCatalog((), ()),
        [nominal],
        [_set()],
    ).definitions[0]
    assert parsed.power_intent.mode is PowerIntentMode.NOMINAL
    assert parsed.power_intent.nominal_dbm == 36.99


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item.update(tags="bad"), "tags must be a string array"),
        (lambda item: item.update(tone="bad"), "tone must be an object"),
        (
            lambda item: item.update(transmit_access={}, receive_squelch=None),
            "must both be objects",
        ),
        (
            lambda item: item.update(tone={"mode": "dtcs", "dtcs_code": 23, "dtcs_polarity": "XX"}),
            "legacy DTCS polarity",
        ),
        (lambda item: item.update(tone={"mode": "pager"}), "unsupported legacy tone mode"),
        (lambda item: item.update(name=""), "name must be a non-empty string"),
        (lambda item: item.update(receive_frequency_hz=True), "must be an integer"),
        (lambda item: item.update(offset_hz="bad"), "must be an integer or null"),
        (lambda item: item.update(notes=42), "must be a string or null"),
        (
            lambda item: item.update(
                tone={"mode": "tone", "encode_hz": "bad"}
            ),
            "must be a number or null",
        ),
    ],
)
def test_invalid_definition_wire_values_are_rejected(
    mutation: object,
    message: str,
) -> None:
    record = deepcopy(_definition())
    mutation(record)  # type: ignore[operator]

    with pytest.raises(ValueError, match=message):
        catalog_with_user_records(FrequencyCatalog((), ()), [record], [])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item.update(members="bad"), "members must be an object array"),
        (lambda item: item.update(name=""), "invalid user frequency set"),
        (
            lambda item: item["members"][0].update(position=-1),
            "invalid user frequency set",
        ),
        (lambda item: item.update(origin="preset"), "must be user-owned"),
    ],
)
def test_invalid_set_wire_values_are_rejected(mutation: object, message: str) -> None:
    record = deepcopy(_set())
    mutation(record)  # type: ignore[operator]

    with pytest.raises(ValueError, match=message):
        catalog_with_user_records(FrequencyCatalog((), ()), [_definition()], [record])
