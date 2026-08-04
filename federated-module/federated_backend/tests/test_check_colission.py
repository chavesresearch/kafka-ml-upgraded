"""Unit tests for the pure matching logic in automl/views.py -
check_colission() and is_blank() - no DB or Kafka needed.

check_colission() compares `dataset_restrictions`/`data_restriction` via
json.loads() on both sides. CLAUDE.md documents a real incident where this
looked like a bug (a first-pass smoke test posted a native dict and
json.loads() crashed on it) and was almost "fixed" by deleting the
json.loads() calls - wrong, because the real clients (FederatedRawSink,
the main trainer's DATA_RESTRICTION env var) always send this field as a
JSON-encoded *string*. These tests lock in that real (string-encoded)
contract so this doesn't get "fixed" again by mistake.
"""

from automl.views import check_colission, is_blank


def _datasource(**overrides):
    base = {
        "input_config": '{"data_reshape": "10"}',
        "dataset_restrictions": "{}",
        "total_msg": 100,
    }
    base.update(overrides)
    return base


def _model(**overrides):
    base = {
        "input_shape": "10",
        "data_restriction": "{}",
        "min_data": 10,
    }
    base.update(overrides)
    return base


def test_is_blank():
    assert is_blank(None) is True
    assert is_blank("") is True
    assert is_blank("x") is False


def test_check_colission_matches_on_string_encoded_json_restrictions():
    # The real wire contract: both restriction fields are JSON-encoded
    # strings, not native dicts - see module docstring.
    assert check_colission(_datasource(), _model(), case=1) is True


def test_check_colission_semantically_equal_but_differently_ordered_json():
    # json.loads() comparison treats these as equal even though the raw
    # strings differ - this is exactly why check_colission decodes both
    # sides instead of doing a raw string comparison.
    ds = _datasource(dataset_restrictions='{"a": 1, "b": 2}')
    model = _model(data_restriction='{"b": 2, "a": 1}')
    assert check_colission(ds, model, case=1) is True


def test_check_colission_mismatched_restrictions_returns_false():
    ds = _datasource(dataset_restrictions='{"a": 1}')
    model = _model(data_restriction='{"a": 2}')
    assert check_colission(ds, model, case=1) is False


def test_check_colission_mismatched_input_shape_returns_false():
    ds = _datasource(input_config='{"data_reshape": "10"}')
    model = _model(input_shape="20")
    assert check_colission(ds, model, case=1) is False


def test_check_colission_case_1_requires_enough_data():
    ds = _datasource(total_msg=5)
    model = _model(min_data=10)
    assert check_colission(ds, model, case=1) is False


def test_check_colission_case_2_incremental_ignores_min_data():
    # Cases 2/4 (incremental) don't gate on total_msg >= min_data at all -
    # an incremental datasource may have no fixed total message count yet.
    ds = _datasource(total_msg=0)
    model = _model(min_data=1000)
    assert check_colission(ds, model, case=2) is True


def test_check_colission_distributed_case_strips_trailing_input_shape_dim():
    # Cases 3/4 (distributed): a >2-element input_shape has its last
    # dimension stripped before comparison (mutates model_item in place).
    ds = _datasource(input_config='{"data_reshape": "10 20"}')
    model = _model(input_shape="10 20 3")
    assert check_colission(ds, model, case=3) is True
    assert model["input_shape"] == "10 20"
