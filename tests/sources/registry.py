"""Tests for src/sources/registry.py."""

from __future__ import annotations

import pytest

from src.sources import get_cls, list_sources, register
from src.sources.base import DataSource
from src.sources.exceptions import UnknownSourceError
from src.sources.registry import reset, restore, snapshot


class FakeSource(DataSource):
    """Test double used to exercise registration mechanics."""

    name = "fake_test_source"

    def fetch(self):  # pragma: no cover - not used here
        raise NotImplementedError

    def load(self, path):  # pragma: no cover - not used here
        raise NotImplementedError


@pytest.fixture
def clean_registry():
    """Opt-in fixture: tests that mutate the registry get a clean slate,
    and the registry is restored to its pre-test state on teardown.

    Tests that need the real bundled registrations (e.g., PEC) should NOT
    request this fixture.
    """
    saved = snapshot()
    reset()
    yield
    restore(saved)


def test_register_returns_class_unchanged(clean_registry):
    assert register(FakeSource) is FakeSource


def test_get_cls_returns_registered_class(clean_registry):
    register(FakeSource)
    assert get_cls("fake_test_source") is FakeSource


def test_get_cls_unknown_raises_with_helpful_message(clean_registry):
    register(FakeSource)
    with pytest.raises(UnknownSourceError) as exc_info:
        get_cls("does_not_exist")
    assert "does_not_exist" in str(exc_info.value)
    assert "fake_test_source" in str(exc_info.value)


def test_list_sources_returns_sorted_names(clean_registry):
    class A(DataSource):
        name = "zeta_source"

        def fetch(self):
            raise NotImplementedError

        def load(self, path):
            raise NotImplementedError

    class B(DataSource):
        name = "alpha_source"

        def fetch(self):
            raise NotImplementedError

        def load(self, path):
            raise NotImplementedError

    register(B)
    register(A)
    assert list_sources() == ["alpha_source", "zeta_source"]


def test_register_without_name_raises(clean_registry):
    class Nameless(DataSource):
        name = ""

        def fetch(self):
            raise NotImplementedError

        def load(self, path):
            raise NotImplementedError

    with pytest.raises(ValueError, match="must define class var `name`"):
        register(Nameless)


def test_register_duplicate_name_raises(clean_registry):
    register(FakeSource)

    class AnotherFake(DataSource):
        name = "fake_test_source"

        def fetch(self):
            raise NotImplementedError

        def load(self, path):
            raise NotImplementedError

    with pytest.raises(ValueError, match="already registered"):
        register(AnotherFake)


def test_ponte_en_carrera_is_registered_at_import_time():
    """Importing src.sources must register all bundled sources.

    Note: PEC is marked deprecated, so it appears only when explicitly
    requested via include_deprecated=True (see test_list_sources_hides_deprecated_by_default).
    """
    import src.sources  # noqa: F401

    assert "ponte_en_carrera" in list_sources(include_deprecated=True)


def test_ponte_en_carrera_resolves_to_correct_class():
    import src.sources  # noqa: F401
    from src.sources.ponte_en_carrera import PonteEnCarreraSource

    assert get_cls("ponte_en_carrera") is PonteEnCarreraSource


def test_list_sources_hides_deprecated_by_default():
    """PEC is marked deprecated; it must not appear in the default list."""
    from src.sources import list_deprecated, list_sources

    active = list_sources()
    deprecated = list_deprecated()
    assert "ponte_en_carrera" in deprecated
    assert "ponte_en_carrera" not in active
    assert set(active).isdisjoint(set(deprecated))


def test_list_sources_include_deprecated_returns_all():
    """With include_deprecated=True, PEC is included alongside active sources."""
    from src.sources import list_sources

    with_deprecated = list_sources(include_deprecated=True)
    without_deprecated = list_sources()
    assert "ponte_en_carrera" in with_deprecated
    assert len(with_deprecated) >= len(without_deprecated)


def test_list_deprecated_returns_sorted_deprecated_names():
    from src.sources import list_deprecated

    deprecated = list_deprecated()
    assert deprecated == sorted(deprecated)
    assert "ponte_en_carrera" in deprecated
