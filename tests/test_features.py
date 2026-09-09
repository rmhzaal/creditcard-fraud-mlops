import pandas as pd
from sklearn.preprocessing import StandardScaler

from src.features import engineer_features


def test_engineer_features_shape_and_no_nans():
    df = pd.DataFrame({
        "Time": [0.0, 1.0, 2.0],
        "Amount": [10.0, 20.0, 30.0],
        "V1": [0.1, 0.2, 0.3],
        "Class": [0, 0, 1],
    })
    result, scaler = engineer_features(df)

    assert result.shape == df.shape
    assert not result.isnull().values.any()
    assert isinstance(scaler, StandardScaler)


def test_engineer_features_reuses_fitted_scaler_without_refitting():
    """Regression test for the train/serve skew bug: applying an already
    -fitted scaler to a single row must not re-fit (which would divide by
    a standard deviation of zero and produce NaN/garbage)."""
    train_df = pd.DataFrame({
        "Time": [0.0, 1.0, 2.0, 3.0],
        "Amount": [10.0, 20.0, 30.0, 40.0],
        "V1": [0.1, 0.2, 0.3, 0.4],
        "Class": [0, 0, 1, 0],
    })
    _, fitted_scaler = engineer_features(train_df)

    single_row = pd.DataFrame({
        "Time": [1.5],
        "Amount": [25.0],
        "V1": [0.15],
        "Class": [0],
    })
    result, returned_scaler = engineer_features(single_row, scaler=fitted_scaler)

    assert not result.isnull().values.any()
    assert returned_scaler is fitted_scaler
