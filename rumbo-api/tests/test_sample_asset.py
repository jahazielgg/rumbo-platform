from app.bootstrap.sample_asset import ensure_sample_floorplan_asset


def test_sample_asset_is_restored_when_upload_is_missing(tmp_path):
    target = ensure_sample_floorplan_asset(tmp_path)

    assert target.is_file()
    assert target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_sample_asset_repairs_stale_or_corrupt_upload(tmp_path):
    target = ensure_sample_floorplan_asset(tmp_path)
    expected = target.read_bytes()

    target.write_bytes(b"corrupt")
    repaired = ensure_sample_floorplan_asset(tmp_path)

    assert repaired == target
    assert repaired.read_bytes() == expected
