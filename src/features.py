import pandas as pd
from sklearn.preprocessing import StandardScaler


def engineer_features(df: pd.DataFrame, scaler: StandardScaler | None = None):
    """Scale Amount and Time; leave the anonymized PCA features (V1-V28) as-is.

    Pass a fitted `scaler` to transform with it unchanged (serving time, or
    a held-out test set). Leave it out to fit a new scaler on this data
    (training time only). Returns the transformed dataframe and the scaler
    that was used, so callers can log/reuse the exact same one.
    """
    df = df.copy()
    if scaler is None:
        scaler = StandardScaler()
        df[["Amount", "Time"]] = scaler.fit_transform(df[["Amount", "Time"]])
    else:
        df[["Amount", "Time"]] = scaler.transform(df[["Amount", "Time"]])
    return df, scaler
