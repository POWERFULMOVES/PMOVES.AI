import copy
import pytest
from schemas import validate_workorder, validate_result
from fixtures import VALID_WORKORDER, VALID_RESULT


def test_valid_workorder_passes():
    validate_workorder(VALID_WORKORDER)  # no raise


def test_workorder_missing_license_ack_raises():
    bad = copy.deepcopy(VALID_WORKORDER)
    del bad["license_ack"]
    with pytest.raises(Exception):
        validate_workorder(bad)


def test_valid_result_passes():
    validate_result(VALID_RESULT)  # no raise


def test_result_bad_status_raises():
    bad = copy.deepcopy(VALID_RESULT)
    bad["status"] = "maybe"
    with pytest.raises(Exception):
        validate_result(bad)
