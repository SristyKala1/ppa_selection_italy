import pandas as pd
import pytest

from ingestion import download_ngfs


class FakeResult:
    def timeseries(self):
        index = pd.MultiIndex.from_tuples(
            [("model_x", "Net Zero 2050", "ITA", "Price|Secondary Energy|Electricity", "US$2010/GJ")],
            names=["model", "scenario", "region", "variable", "unit"],
        )
        return pd.DataFrame({2020: [24.7], 2025: [22.5]}, index=index)


class FakeConnection:
    def __init__(self, platform):
        self.platform = platform

    def query(self, **kwargs):
        return FakeResult()


class BrokenConnection:
    def __init__(self, platform):
        raise ConnectionError("simulated network failure")


def test_skips_when_already_downloaded(tmp_path, monkeypatch):
    output = tmp_path / "ngfs_price_ita.csv"
    output.write_text("already here")
    monkeypatch.setattr(download_ngfs, "OUTPUT_PATH", output)
    monkeypatch.setattr(download_ngfs.pyam.iiasa, "Connection", FakeConnection)

    download_ngfs.download_ngfs_prices()

    assert output.read_text() == "already here"


def test_downloads_and_writes_a_wide_csv(tmp_path, monkeypatch):
    output = tmp_path / "prices" / "ngfs_price_ita.csv"
    monkeypatch.setattr(download_ngfs, "OUTPUT_PATH", output)
    monkeypatch.setattr(download_ngfs.pyam.iiasa, "Connection", FakeConnection)

    download_ngfs.download_ngfs_prices()

    df = pd.read_csv(output)
    assert list(df.columns) == ["Model", "Scenario", "Region", "Variable", "Unit", "2020", "2025"]
    assert df.loc[0, "Scenario"] == "Net Zero 2050"


def test_raises_a_clear_error_when_the_platform_is_unreachable(tmp_path, monkeypatch):
    output = tmp_path / "ngfs_price_ita.csv"
    monkeypatch.setattr(download_ngfs, "OUTPUT_PATH", output)
    monkeypatch.setattr(download_ngfs.pyam.iiasa, "Connection", BrokenConnection)

    with pytest.raises(RuntimeError):
        download_ngfs.download_ngfs_prices()
