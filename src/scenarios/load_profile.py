from pathlib import Path
import tempfile
import urllib.request
import zipfile

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_LOAD_DIR = PROJECT_ROOT / "data" / "raw" / "load" / "elmas"

ELMAS_ZIP_URL = "https://ndownloader.figshare.com/files/41895786"

ARCHETYPES = {
    "data_center": ("63.11", "MV"),
    "heavy_manufacturing": ("24.10", "MV"),
    "chemicals": ("20.14", "MV"),
    "pharmaceutical": ("21.20", "MV"),
    "automotive": ("29.10", "MV"),
    "food_beverage": ("10.1", "MV"),
    "retail": ("47.11", "MV"),
    "office_services": ("70.10", "MV"),
    "hospital": ("86.10", "MV"),
}


def download_elmas():
    RAW_LOAD_DIR.mkdir(parents=True, exist_ok=True)
    if (RAW_LOAD_DIR / "Time_series_18_clusters.csv").exists():
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "ELMAS_dataset.zip"
        urllib.request.urlretrieve(ELMAS_ZIP_URL, zip_path)

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        extracted_dir = Path(tmp_dir) / "ELMAS_dataset"
        for filename in ["Time_series_18_clusters.csv", "Clusters_after_manual_reclassification.csv"]:
            (extracted_dir / filename).rename(RAW_LOAD_DIR / filename)


download_elmas()

clusters = pd.read_csv(
    RAW_LOAD_DIR / "Time_series_18_clusters.csv",
    sep=";",
    decimal=",",
    index_col=0,
)
clusters.index = pd.to_datetime(clusters.index)

cluster_map = pd.read_csv(RAW_LOAD_DIR / "Clusters_after_manual_reclassification.csv", sep=";")


def synthetic_load_profile(nace_class, power_level, annual_kwh):
    cluster = cluster_map[
        (cluster_map["Class"] == nace_class) & (cluster_map["Power_level"] == power_level)
    ]["Cluster"].iloc[0]

    shape = clusters[str(cluster)]
    shape = shape / shape.sum()
    return shape * annual_kwh


def load_profile_for_archetype(archetype, annual_kwh):
    if archetype not in ARCHETYPES:
        raise ValueError(f"unknown archetype '{archetype}', expected one of {list(ARCHETYPES)}")
    if annual_kwh <= 0:
        raise ValueError(f"annual_kwh must be positive, got {annual_kwh}")
    nace_class, power_level = ARCHETYPES[archetype]
    return synthetic_load_profile(nace_class, power_level, annual_kwh)
