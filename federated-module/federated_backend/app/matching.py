import json
from typing import Any


def is_blank(attribute: str | None) -> bool:
    """Checks if the attribute is an empty string or None."""
    return attribute is None or attribute == ""


def check_colission(datasource_item: dict[str, Any], model_item: dict[str, Any], case: int) -> bool:
    """Checks if a datasource and a model are compatible for training.

    Ported unchanged from the original Django ``automl/views.py`` (see
    federated-module/CLAUDE.md) - both restriction fields are compared as
    JSON-encoded *strings*, decoded with ``json.loads()`` here (not native
    dicts - see app/models.py's docstring for why this is the real wire
    format, not a bug). ``case`` uses this module's own local 1-5 numbering
    (federated_model_training/tensorflow/utils.py's scheme: 1=single,
    2=single incremental, 3=distributed, 4=distributed incremental,
    5=blockchain) - distinct from the main trainer's global 1-9 CASE enum.
    """
    ds_input_config = json.loads(datasource_item["input_config"])

    # Distributed models: input shape conversion. A >2-element input_shape
    # has its trailing dimension stripped before comparison (mutates
    # model_item in place, matching the original).
    aux_array = model_item["input_shape"].split()
    if case in (3, 4) and len(aux_array) > 2:
        model_item["input_shape"] = " ".join(aux_array[:-1])

    if ds_input_config["data_reshape"] == model_item["input_shape"] and json.loads(
        datasource_item["dataset_restrictions"]
    ) == json.loads(model_item["data_restriction"]):
        if (case in (1, 3, 5) and datasource_item["total_msg"] >= model_item["min_data"]) or case in (2, 4):
            return True

    return False
