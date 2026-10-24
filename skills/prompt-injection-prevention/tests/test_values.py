from prompt_injection_prevention import (
    EVERYONE,
    USER,
    Readers,
    Source,
    trusted,
    untrusted,
)


def test_trusted_values_come_from_the_user() -> None:
    v = trusted("hi")
    assert v.trusted
    assert v.sources == {USER}


def test_untrusted_values_name_their_source() -> None:
    v = untrusted("hi", "web")
    assert not v.trusted
    assert v.sources == {Source("web", trusted=False)}


def test_derived_values_keep_every_source_and_the_narrowest_readers() -> None:
    a = trusted(2, Readers({"a@x.com", "b@x.com"}))
    b = untrusted(3, "email", Readers({"b@x.com"}))
    c = a.derive(a.value + b.value, b)
    assert c.value == 5
    assert not c.trusted
    assert c.sources == a.sources | b.sources
    assert c.readers == Readers({"b@x.com"})


def test_everyone_is_the_identity_for_readers() -> None:
    r = Readers({"a"})
    assert (EVERYONE & r) == r
    assert (r & EVERYONE) == r
    assert EVERYONE.allows("anyone")
    assert not r.allows("b")
