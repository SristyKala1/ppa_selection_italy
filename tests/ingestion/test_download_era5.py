import zipfile

import pytest

from ingestion import download_era5


class FakeClient:
    def __init__(self, fails=0):
        self.fails = fails
        self.calls = 0

    def retrieve(self, dataset, request, target):
        self.calls += 1
        if self.calls <= self.fails:
            raise RuntimeError("simulated CDS API failure")
        with zipfile.ZipFile(target, "w") as zf:
            zf.writestr("reanalysis-era5-single-levels-timeseries-sfc_fake.nc", b"fake netcdf bytes")


def test_skips_when_already_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(download_era5, "RAW_WEATHER_DIR", tmp_path)
    (tmp_path / "era5_nord_torino.nc").write_bytes(b"already here")

    client = FakeClient()
    result = download_era5.download_city(client, "nord", "torino", 45.07, 7.68)

    assert result is True
    assert client.calls == 0


def test_downloads_and_renames_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(download_era5, "RAW_WEATHER_DIR", tmp_path)

    client = FakeClient()
    result = download_era5.download_city(client, "nord", "torino", 45.07, 7.68)

    assert result is True
    assert client.calls == 1
    assert (tmp_path / "era5_nord_torino.nc").exists()
    assert not list(tmp_path.glob("_tmp_*.zip"))


def test_retries_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(download_era5, "RAW_WEATHER_DIR", tmp_path)
    monkeypatch.setattr(download_era5, "RETRY_PAUSE_SECONDS", 0)

    client = FakeClient(fails=2)
    result = download_era5.download_city(client, "nord", "torino", 45.07, 7.68)

    assert result is True
    assert client.calls == 3
    assert (tmp_path / "era5_nord_torino.nc").exists()


def test_gives_up_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(download_era5, "RAW_WEATHER_DIR", tmp_path)
    monkeypatch.setattr(download_era5, "RETRY_PAUSE_SECONDS", 0)

    client = FakeClient(fails=99)
    result = download_era5.download_city(client, "nord", "torino", 45.07, 7.68)

    assert result is False
    assert client.calls == download_era5.MAX_RETRIES
    assert not (tmp_path / "era5_nord_torino.nc").exists()
    assert not list(tmp_path.glob("_tmp_*.zip"))
