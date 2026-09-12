from app.importer.normalize import nkey, split_party


def test_nkey_unescapes_and_normalizes_without_guessing() -> None:
    assert nkey(" Meenakshi &amp; Co. ") == "MEENAKSHIANDCO"


def test_split_party_handles_step_and_care_of_variants() -> None:
    parts = split_party("GAUTHAM LEATHER INDUSTRIES C/O, HAJI JAMAL MOHAMED - STEP")
    assert parts.left == "GAUTHAM LEATHER INDUSTRIES"
    assert parts.right == "HAJI JAMAL MOHAMED"
    assert parts.is_step is True


def test_split_party_without_care_of() -> None:
    parts = split_party("Vaigai Leather Corporation A-Unit-STEP")
    assert parts.cleaned == "Vaigai Leather Corporation A-Unit"
    assert parts.right is None
    assert parts.is_step is True

