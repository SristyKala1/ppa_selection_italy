import pandas as pd


def read_timeseries_csv(path):
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("Europe/Rome")
    return df
