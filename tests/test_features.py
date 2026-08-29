import pandas as pd
from src.features import engineer_features


def test_engineer_features_shape_and_no_nans():
    df = pd.DataFrame({
        "Time": [0.0, 1.0, 2.0],
        "Amount": [10.0, 20.0, 30.0],
        "V1": [0.1, 0.2, 0.3],
        "Class": [0, 0, 1],
    })
    result = engineer_features(df)

    assert result.shape == df.shape
    assert not result.isnull().values.any()
