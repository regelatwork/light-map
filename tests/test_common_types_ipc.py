from light_map.common_types import DetectionResult, ResultType


def test_detection_result_serialization():
    # Verify we can create and represent the new types
    res = DetectionResult(timestamp=123456, type=ResultType.ARUCO, data={"ids": [1]})
    assert res.timestamp == 123456
    assert res.type == ResultType.ARUCO
