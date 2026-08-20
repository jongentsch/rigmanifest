from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from chirp import chirp_common, memmap
from chirp.drivers.vx6 import POWER_LEVELS, VX6Radio

from rigmanifest.chirp_image import (
    _compiled_to_chirp,
    _power_level,
    _setting_count,
    image_memory_validator,
    import_chirp_image,
    load_chirp_image,
    write_compiled_image,
)
from rigmanifest.compiler import compile_profiles
from rigmanifest.ipc import handle_request
from rigmanifest.models import (
    CatalogOrigin,
    CompilationSettings,
    CompiledMemory,
    FrequencyCatalog,
    FrequencySet,
    FrequencySetMember,
    Mode,
    Priority,
    Profile,
    SignalingSpec,
    TransmitBehavior,
)


def _vx6_image(path: Path) -> Path:
    radio = VX6Radio(None)
    radio._mmap = memmap.MemoryMapBytes(b"\x00" * radio._memsize)
    radio.process_mmap()
    for index, bank in enumerate(radio._memobj.banks):
        radio._memobj.bank_used[index].in_use = 0xFFFF
        for member_index in range(len(bank.channels)):
            bank.channels[member_index] = 0xFFFF

    for number, name, frequency, skip in (
        (1, "LOCAL", 146_910_000, ""),
        (2, "CALL", 146_520_000, "S"),
        (3, "TRAVEL", 147_300_000, ""),
    ):
        memory = chirp_common.Memory()
        memory.number = number
        memory.empty = False
        memory.name = name
        memory.freq = frequency
        memory.duplex = "-" if number == 1 else ""
        memory.offset = 600_000 if number == 1 else 0
        memory.mode = "FM"
        memory.tmode = ""
        memory.power = POWER_LEVELS[0]
        memory.tuning_step = 5.0
        memory.skip = skip
        radio.set_memory(memory)

    bank_model = radio.get_bank_model()
    local = bank_model.get_mappings()[0]
    local.set_name("LOCAL")
    for number in (1, 2):
        bank_model.add_memory_to_mapping(radio.get_memory(number), local)
    radio.save(str(path))
    return path


def test_image_import_uses_chirp_model_memories_and_banks(tmp_path: Path) -> None:
    imported = import_chirp_image(
        _vx6_image(tmp_path / "source.img"),
        radio_id="handheld",
    )

    assert imported.driver_reference == "Yaesu_VX-6"
    assert imported.target.manufacturer == "Yaesu"
    assert imported.target.model == "VX-6"
    assert imported.target.capabilities.bank_count == 24
    assert imported.definition_count == 3
    assert [(item.name, len(item.members)) for item in imported.frequency_sets] == [
        ("LOCAL", 2),
        ("Unbanked memories", 1),
    ]
    assert imported.profile.frequency_set_ids == (imported.frequency_sets[0].id,)
    assert imported.profile.frequency_definition_ids == (
        imported.frequency_definitions[2].id,
    )
    calling = imported.frequency_definitions[1]
    assert calling.power_label == "Hi"
    assert calling.scan_skip == "S"
    assert calling.tuning_step_hz == 5_000


def test_compiled_image_is_saved_by_chirp_with_bank_membership(tmp_path: Path) -> None:
    source = _vx6_image(tmp_path / "source.img")
    imported = import_chirp_image(source, radio_id="handheld")
    radio = load_chirp_image(source)
    plan = compile_profiles(
        FrequencyCatalog(imported.frequency_definitions, imported.frequency_sets),
        (imported.profile,),
        imported.target,
        CompilationSettings(map_sets_to_banks=True),
        memory_validator=image_memory_validator(radio),
    )
    output = tmp_path / "compiled.img"

    write_compiled_image(
        plan,
        source,
        output,
        bank_names={item.id: item.name for item in imported.frequency_sets},
    )

    reloaded = import_chirp_image(output, radio_id="roundtrip")
    assert reloaded.definition_count == 3
    assert [(item.name, len(item.members)) for item in reloaded.frequency_sets] == [
        ("LOCAL", 2),
        ("Unbanked memories", 1),
    ]
    assert reloaded.frequency_definitions[1].scan_skip == "S"
    assert reloaded.frequency_definitions[1].power_label == "Hi"


def test_image_bank_order_comes_from_profile_not_memory_priority(tmp_path: Path) -> None:
    source = _vx6_image(tmp_path / "source.img")
    imported = import_chirp_image(source, radio_id="handheld")
    first_definition = imported.frequency_definitions[0]
    second_definition = replace(
        imported.frequency_definitions[1],
        priority=Priority.MANDATORY,
    )
    first_set = FrequencySet(
        "first-bank",
        "FIRST",
        CatalogOrigin.USER,
        (FrequencySetMember(first_definition.id, 0),),
    )
    second_set = FrequencySet(
        "second-bank",
        "SECOND",
        CatalogOrigin.USER,
        (FrequencySetMember(second_definition.id, 0),),
    )
    plan = compile_profiles(
        FrequencyCatalog(
            (first_definition, second_definition),
            (first_set, second_set),
        ),
        (Profile("ordered", "Ordered", (first_set.id, second_set.id)),),
        imported.target,
        CompilationSettings(map_sets_to_banks=True),
    )
    assert [memory.source_frequency_definition_id for memory in plan.memories] == [
        second_definition.id,
        first_definition.id,
    ]
    assert [bank.frequency_set_id for bank in plan.banks] == [
        first_set.id,
        second_set.id,
    ]
    output = tmp_path / "compiled.img"

    write_compiled_image(
        plan,
        source,
        output,
        bank_names={first_set.id: first_set.name, second_set.id: second_set.name},
    )

    radio = load_chirp_image(output)
    mappings = radio.get_bank_model().get_mappings()
    assert mappings[0].get_name() == "FIRST"
    assert mappings[1].get_name() == "SECOND"
    assert [
        int(memory.number)
        for memory in radio.get_bank_model().get_mapping_memories(mappings[0])
    ] == [2]
    assert [
        int(memory.number)
        for memory in radio.get_bank_model().get_mapping_memories(mappings[1])
    ] == [1]


def test_compiled_image_erases_unselected_regular_memories(tmp_path: Path) -> None:
    source = _vx6_image(tmp_path / "source.img")
    imported = import_chirp_image(source, radio_id="handheld")
    bank_profile = imported.profile.__class__(
        id="bank-only",
        name="Bank only",
        frequency_set_ids=(imported.frequency_sets[0].id,),
    )
    plan = compile_profiles(
        FrequencyCatalog(imported.frequency_definitions, imported.frequency_sets),
        (bank_profile,),
        imported.target,
        CompilationSettings(map_sets_to_banks=True),
    )
    output = tmp_path / "compiled.img"

    write_compiled_image(
        plan,
        source,
        output,
        bank_names={item.id: item.name for item in imported.frequency_sets},
    )

    radio = load_chirp_image(output)
    assert not radio.get_memory(1).empty
    assert not radio.get_memory(2).empty
    assert radio.get_memory(3).empty


def test_image_export_refuses_to_overwrite_the_source(tmp_path: Path) -> None:
    source = _vx6_image(tmp_path / "source.img")
    imported = import_chirp_image(source, radio_id="handheld")
    plan = compile_profiles(
        FrequencyCatalog(imported.frequency_definitions, imported.frequency_sets),
        (imported.profile,),
        imported.target,
    )

    try:
        write_compiled_image(
            plan,
            source,
            source,
            bank_names={item.id: item.name for item in imported.frequency_sets},
        )
    except ValueError as error:
        assert "must not overwrite" in str(error)
    else:
        raise AssertionError("source overwrite should be rejected")


def test_image_import_and_compile_are_available_through_ipc(tmp_path: Path) -> None:
    database = tmp_path / "workspace.sqlite3"
    source = _vx6_image(tmp_path / "source.img")
    imported_response = handle_request(
        {
            "id": "import-image",
            "method": "import_chirp_image",
            "params": {
                "database_path": str(database),
                "radio_id": "handheld",
                "source_path": str(source),
            },
        }
    )
    assert "error" not in imported_response
    imported = imported_response["result"]
    assert imported["driver_reference"] == "Yaesu_VX-6"
    assert imported["bank_count"] == 24
    assert imported["image_version"]["kind"] == "source"
    assert Path(imported["image_version"]["path"]).is_file()

    output = tmp_path / "compiled.img"
    compiled = handle_request(
        {
            "id": "compile-image",
            "method": "compile",
            "params": {
                "database_path": str(database),
                "radio_id": "handheld",
                "profiles": [imported["profile"]],
                "additional_frequency_set_ids": [],
                "additional_frequency_definition_ids": [],
                "user_frequency_definitions": imported["frequency_definitions"],
                "user_frequency_sets": imported["frequency_sets"],
                "output_path": str(output),
                "memory_start": 1,
                "map_sets_to_banks": True,
                "use_factory_sets": False,
            },
        }
    )

    assert "error" not in compiled
    assert compiled["result"]["summary"]["programmed"] == 3
    assert compiled["result"]["image_path"] == str(output)
    assert compiled["result"]["image_version"]["kind"] == "compiled"
    assert Path(compiled["result"]["managed_image_path"]).is_file()
    assert output.is_file()
    versions = handle_request(
        {
            "id": "list-images",
            "method": "list_radio_images",
            "params": {
                "database_path": str(database),
                "radio_id": "handheld",
            },
        }
    )["result"]["versions"]
    assert [item["kind"] for item in versions] == ["compiled", "source"]


@pytest.mark.parametrize(
    ("filename", "radio_id", "message"),
    [
        ("source.csv", "radio", "requires"),
        ("missing.img", "radio", "does not exist"),
        ("source.img", " ", "must not be blank"),
    ],
)
def test_image_import_validates_its_inputs(
    tmp_path: Path, filename: str, radio_id: str, message: str
) -> None:
    path = tmp_path / filename
    if filename == "source.img":
        path.write_bytes(b"image")

    with pytest.raises(ValueError, match=message):
        import_chirp_image(path, radio_id=radio_id)


def _compiled_memory(**changes) -> CompiledMemory:
    memory = CompiledMemory(
        source_frequency_definition_id="frequency",
        source_frequency_set_ids=(),
        memory_number=1,
        target_name="TEST",
        receive_frequency_hz=146_520_000,
        transmit_behavior=TransmitBehavior.SAME,
        transmit_frequency_hz=None,
        offset_hz=None,
        mode=Mode.FM,
        transmit_access=SignalingSpec(),
        receive_squelch=SignalingSpec(),
        tuning_step_hz=5_000,
    )
    return replace(memory, **changes)


@pytest.mark.parametrize(
    ("memory", "duplex", "offset"),
    [
        (_compiled_memory(transmit_behavior=TransmitBehavior.DISABLED), "off", 0),
        (
            _compiled_memory(
                transmit_behavior=TransmitBehavior.SPLIT,
                transmit_frequency_hz=145_000_000,
            ),
            "split",
            145_000_000,
        ),
        (
            _compiled_memory(
                transmit_behavior=TransmitBehavior.OFFSET,
                offset_hz=-600_000,
            ),
            "-",
            600_000,
        ),
    ],
)
def test_compiled_memory_transmit_modes_map_to_chirp(memory, duplex, offset) -> None:
    features = SimpleNamespace(
        valid_skips=[""],
        valid_tuning_steps=[5.0],
        valid_power_levels=[],
    )

    converted = _compiled_to_chirp(memory, features, None)

    assert (converted.duplex, converted.offset) == (duplex, offset)


def test_power_selection_supports_fallback_label_and_nearest_level() -> None:
    low = chirp_common.PowerLevel("Low", watts=1)
    high = chirp_common.PowerLevel("High", watts=5)
    features = SimpleNamespace(valid_power_levels=[low, high])

    assert _power_level(_compiled_memory(), features, "fallback") == "fallback"
    assert _power_level(
        _compiled_memory(power_dbm=float(high), power_label="High"),
        features,
        None,
    ) is high
    assert _power_level(
        _compiled_memory(power_dbm=float(low) + 0.1, power_label="Unknown"),
        features,
        None,
    ) is low


def test_setting_count_handles_radios_without_settings() -> None:
    radio = SimpleNamespace(get_features=lambda: SimpleNamespace(has_settings=False))

    assert _setting_count(radio) == 0
