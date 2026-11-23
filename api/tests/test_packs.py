import pytest

from sigil.packs import (
    DEFAULT_PACKS_DIR,
    DetailsError,
    load_packs,
    pack_by_code,
    validate_details,
)


@pytest.fixture(scope="module")
def packs():
    return load_packs(DEFAULT_PACKS_DIR)


def test_all_expected_packs_load(packs):
    assert set(packs) == {"generic", "medicine", "cosmetics", "food", "precious"}
    assert [pack_by_code(packs, c).id for c in range(5)] == [
        "generic",
        "medicine",
        "cosmetics",
        "food",
        "precious",
    ]


def test_expiry_requirements(packs):
    assert packs["medicine"].expiry_required is True
    assert packs["food"].expiry_required is True
    assert packs["cosmetics"].expiry_required is False
    assert packs["precious"].expiry_required is False


def test_medicine_details_are_normalised(packs):
    details = validate_details(
        packs["medicine"],
        {
            "product_name": "  Paracetamol 500mg ",
            "manufacturer": "Acme Pharma",
            "regulator_registration_number": "NAFDAC-1234",
            "batch_number": "B-2026-001",
            "manufacture_date": "2026-01-10",
            "expiry_date": "2028-01-10",
            "photo": "/uploads/acme.jpg",
        },
    )
    assert details["product_name"] == "Paracetamol 500mg"
    assert details["manufacture_date"] == "2026-01-10"


def test_missing_required_field_is_reported(packs):
    with pytest.raises(DetailsError) as exc:
        validate_details(
            packs["medicine"],
            {
                "product_name": "Paracetamol",
                "manufacturer": "Acme",
                "regulator_registration_number": "X",
                "batch_number": "B1",
                "manufacture_date": "2026-01-10",
                "photo": "/x.jpg",
            },
        )
    assert "expiry_date" in exc.value.errors


def test_unknown_field_is_rejected(packs):
    with pytest.raises(DetailsError) as exc:
        validate_details(
            packs["precious"],
            {
                "item_type": "Gold bar",
                "weight": "100",
                "purity": "999.9",
                "certificate_reference": "C-1",
                "photo": "/gold.jpg",
                "colour": "yellow",
            },
        )
    assert "colour" in exc.value.errors


def test_number_is_stored_as_a_plain_string(packs):
    details = validate_details(
        packs["precious"],
        {
            "item_type": "Gold bar",
            "weight": "12.50",
            "purity": "999.9",
            "certificate_reference": "C-1",
            "photo": "/gold.jpg",
        },
    )
    assert details["weight"] == "12.5"


def test_bad_date_and_number_are_rejected(packs):
    with pytest.raises(DetailsError) as exc:
        validate_details(
            packs["precious"],
            {
                "item_type": "Gold bar",
                "weight": "-2",
                "purity": "999.9",
                "certificate_reference": "C-1",
                "photo": "/gold.jpg",
            },
        )
    assert "weight" in exc.value.errors

    with pytest.raises(DetailsError) as exc:
        validate_details(
            packs["food"],
            {
                "product_name": "Milk",
                "batch_number": "B1",
                "production_date": "10/01/2026",
                "expiry_date": "2026-02-01",
                "photo": "/milk.jpg",
            },
        )
    assert "production_date" in exc.value.errors


def test_optional_field_may_be_absent(packs):
    details = validate_details(
        packs["cosmetics"],
        {
            "brand": "Glow",
            "product_name": "Lip balm",
            "batch_number": "C-1",
            "photo": "/lip.jpg",
        },
    )
    assert "expiry_date" not in details
