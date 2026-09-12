from pathlib import Path

import pytest

from app.importer.masters import load_master_directory


FIXTURES = Path(__file__).parent / "fixtures"

# Explicit acceptance mappings for legacy Tally ledger spellings. These simulate
# admin-approved aliases; matcher.suggest() is never used to create them.
APPROVED_ALIASES = {
    "S.S.International  (Exports) Tanning": 18,
    "Vaigai Leather Corporation A-Unit": 29,
    "Sea Lord Leathers - Subramanian & Co": 3,
    "K.Mohamed Muthu Sons(KMA-Begam)": 6,
    "K.A.R Leathers (P) Ltd - Unit 1": 16,
    "Khaja Moideen Leather Company (MMMT)": 21,
    "K.A.R.Leathers P Ltd- Unit -2": 33,
    "Super Tanning Compa C/o.K.Kaja Maideen Tannery": 38,
    "S.S.International(CHE) C/o.K.M.Ashraf Nisa Dry Shop": 34,
    "S.M.A.Tanners C/o.M.Raviyathammal Tannery": 25,
    "Aasim Leather Exports C/o.Mubarak Leather Exports-B": 13,
    "S.M.A. Tannery C/O. S.Mohamed Abdullah Tannery": 39,
}


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def tanneries(fixtures_dir):
    return load_master_directory(fixtures_dir)

