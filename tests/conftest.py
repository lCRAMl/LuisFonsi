import pytest

from palletizer.model import Inputs
from palletizer.patterns import PatternLibrary


@pytest.fixture(scope="session")
def library() -> PatternLibrary:
    return PatternLibrary.load()


def make_inputs(pattern: str, box_conv: float, box_cross: float, **kwargs) -> Inputs:
    return Inputs(box_length_conv=box_conv, box_width_conv=box_cross, pattern=pattern, **kwargs)
