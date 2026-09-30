import pytest

from palletizer.constants import DIR_X, DIR_Y
from palletizer.transform import angle_to_output, point_to_output, vector_to_output


@pytest.mark.parametrize("corner, expected", [
    (1, (340, 660)), (2, (860, 660)), (3, (860, 140)), (4, (340, 140)),
])
def test_point_mirroring(corner, expected):
    assert point_to_output(340, 660, corner, 1200, 800) == expected


@pytest.mark.parametrize("corner", [1, 2, 3, 4])
@pytest.mark.parametrize("k", range(8))
def test_angle_matches_mirrored_vector(corner, k):
    """Der umgerechnete Winkel muss zum gespiegelten Richtungsvektor passen."""
    dx, dy = vector_to_output(DIR_X[k], DIR_Y[k], corner)
    angle = angle_to_output(k * 45, corner)
    j = angle // 45
    assert angle % 45 == 0
    assert DIR_X[j] == pytest.approx(dx)
    assert DIR_Y[j] == pytest.approx(dy)
