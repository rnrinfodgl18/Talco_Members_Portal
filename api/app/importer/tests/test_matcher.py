from app.importer.matcher import resolve, suggest

from .conftest import APPROVED_ALIASES


def test_all_august_rows_resolve_without_fuzzy_matching(fixtures_dir, tanneries) -> None:
    from app.importer.parser import parse_file

    resolutions = [
        resolve(row.party, tanneries, APPROVED_ALIASES)
        for filename in ("Treatment.xml", "Chrome.xml", "Sludge.xml", "Receipt.xml")
        for row in parse_file(fixtures_dir / filename)
    ]
    assert all(item.matched for item in resolutions)
    assert all(item.method != "fuzzy" for item in resolutions)


def test_receipts_resolve_to_32_distinct_tanneries(fixtures_dir, tanneries) -> None:
    from app.importer.parser import parse_file

    resolved = [resolve(row.party, tanneries, APPROVED_ALIASES) for row in parse_file(fixtures_dir / "Receipt.xml")]
    assert len({item.tannery.sno for item in resolved if item.tannery}) == 32


def test_reversed_care_of_cases_choose_the_matching_side(tanneries) -> None:
    assert resolve("IRWINTANNING COMPANY C/o. Sree Rajeshwari Leathers", tanneries).tannery.sno == 32
    assert resolve("GAUTHAM LEATHER INDUSTRIES C/O, HAJI JAMAL MOHAMED", tanneries).tannery.sno == 19
    assert resolve("S.K.Leather Corporation C/o.Thaya Tanning Company", tanneries).tannery.sno == 22


def test_step_and_non_step_resolve_same_tannery(tanneries) -> None:
    plain = resolve("Vaigai Leather Corporation A-Unit", tanneries, APPROVED_ALIASES)
    step = resolve("Vaigai Leather Corporation A-Unit-STEP", tanneries, APPROVED_ALIASES)
    assert plain.tannery.sno == step.tannery.sno == 29
    assert plain.is_step is False
    assert step.is_step is True


def test_unknown_name_stays_queued_after_suggestions(tanneries) -> None:
    party = "Xyz Leathers C/o. Abc Tannery"
    before = resolve(party, tanneries)
    suggestions = suggest(party, tanneries)
    after = resolve(party, tanneries)
    assert before.matched is after.matched is False
    assert before.method == after.method == "queue"
    assert len(suggestions) == 3
    assert len({item.sno for item in suggestions}) == 3

