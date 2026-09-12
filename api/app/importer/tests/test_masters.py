from collections import Counter


def test_real_workbooks_load_all_40_tanneries(tanneries) -> None:
    assert len(tanneries) == 40
    assert Counter(item.pump_house for item in tanneries) == {
        "A": 10,
        "B": 8,
        "C": 15,
        "D": 5,
        "E": 2,
    }
    assert [item.sno for item in tanneries] == list(range(1, 41))


def test_master_fields_are_loaded(tanneries) -> None:
    saddique = next(item for item in tanneries if item.sno == 1)
    assert saddique.name == "SADDIQUE LEATHERS - A UNIT"
    assert saddique.internal_id == "TNDGL/TAN/0009"
    assert saddique.gstin == "33AAEFS8887P1Z7"
    assert saddique.original_shares == 7795

