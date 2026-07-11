from causal_emergence_zoo.temporal import derive_temporal_features, temporal_feature_names


def test_temporal_features_do_not_cross_trajectory_boundaries():
    rows = [
        ("a", 0.0, [1.0]),
        ("a", 1.0, [3.0]),
        ("a", 2.0, [6.0]),
        ("b", 0.0, [10.0]),
        ("b", 1.0, [14.0]),
    ]
    transformed = list(derive_temporal_features(rows, feature_names=["x"], differences=[1], volatility_windows=[2]))
    assert transformed == [("a", 1.0, [3.0, 2.0, 1.0]), ("a", 2.0, [6.0, 3.0, 1.5]), ("b", 1.0, [14.0, 4.0, 2.0])]
    assert temporal_feature_names(["x"], differences=[1], volatility_windows=[2]) == ["x", "delta_lag_1:x", "volatility_window_2:x"]
