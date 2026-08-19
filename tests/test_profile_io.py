from __future__ import annotations

import pytest

from rigmanifest.fixtures import BUILTIN_CATALOG
from rigmanifest.profile_io import profile_to_dict, profiles_from_records


def profile_record(**changes: object) -> dict[str, object]:
    return {
        "id": "travel",
        "name": "Travel",
        "description": "",
        "frequency_set_ids": ["us-noaa-weather"],
        "frequency_definition_ids": ["us-noaa-weather-1"],
        "frequency_plan_id": "arrl-us-national",
        **changes,
    }


def test_profiles_round_trip_and_optional_fields_default() -> None:
    parsed = profiles_from_records(
        [{"id": "empty", "name": "Empty"}],
        BUILTIN_CATALOG,
    )

    assert profile_to_dict(parsed[0]) == {
        "id": "empty",
        "name": "Empty",
        "description": "",
        "frequency_set_ids": [],
        "frequency_definition_ids": [],
        "frequency_plan_id": None,
    }


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([profile_record(), profile_record()], "duplicate ID"),
        ([profile_record(frequency_set_ids=["missing"])], "unknown frequency set"),
        (
            [profile_record(frequency_definition_ids=["missing"])],
            "unknown frequency definition",
        ),
        ([profile_record(frequency_plan_id="missing")], "unknown frequency plan"),
        ([profile_record(frequency_plan_id=1)], "frequency_plan_id"),
        ([profile_record(description=1)], "description"),
        ([profile_record(name="")], "profile name"),
        (
            [profile_record(frequency_set_ids=["us-noaa-weather", "us-noaa-weather"])],
            "invalid profile",
        ),
        ([profile_record(frequency_set_ids="bad")], "string array"),
        ([profile_record(frequency_definition_ids=[""])], "string array"),
    ],
)
def test_invalid_profile_records_are_rejected(
    records: list[dict[str, object]],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        profiles_from_records(records, BUILTIN_CATALOG)
