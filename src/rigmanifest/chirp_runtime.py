"""Headless CHIRP initialization shared by source and frozen runtimes."""

from __future__ import annotations

import builtins
import gettext
import logging
import pkgutil
from functools import lru_cache
from importlib import import_module, resources
from typing import Iterable

from chirp import directory
import chirp.drivers


LOG = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def initialize_chirp_runtime() -> None:
    """Install CHIRP's headless translations and register bundled drivers."""

    _install_translations()
    for module_name in _bundled_driver_modules():
        try:
            import_module(module_name)
        except Exception as error:
            # Match CHIRP's normal discovery behavior: one broken optional
            # driver must not make every other image unavailable.
            LOG.warning("Failed to import CHIRP driver module %s: %s", module_name, error)


def chirp_runtime_status(
    required_driver_references: Iterable[str] = (),
) -> dict[str, object]:
    """Return package-smoke facts without exposing CHIRP internals to the UI."""

    initialize_chirp_runtime()
    registered = frozenset(directory.DRV_TO_RADIO)
    required = tuple(dict.fromkeys(required_driver_references))
    return {
        "registered_driver_count": len(registered),
        "translations_ready": (
            callable(getattr(builtins, "_", None))
            and callable(getattr(builtins, "ngettext", None))
        ),
        "missing_driver_references": [
            reference for reference in required if reference not in registered
        ],
    }


def _install_translations() -> None:
    """Provide the builtins that CHIRP drivers expect outside the wxPython UI."""

    locale_directory = resources.files("chirp").joinpath("locale")
    translation = gettext.translation(
        "CHIRP",
        localedir=str(locale_directory),
        fallback=True,
    )
    translation.install(names=("ngettext",))


def _bundled_driver_modules() -> tuple[str, ...]:
    """List drivers from source files or a PyInstaller module archive."""

    prefix = f"{chirp.drivers.__name__}."
    module_names = {
        f"{prefix}{name}" for name in getattr(chirp.drivers, "__all__", ())
    }
    module_names.update(
        module.name
        for module in pkgutil.iter_modules(chirp.drivers.__path__, prefix)
    )
    return tuple(sorted(module_names))
