from __future__ import annotations

import time
from typing import Any

import httpx


class KafkaMLError(RuntimeError):
    """Raised when a Kafka-ML backend request fails.

    Carries the HTTP status code and response body so callers can inspect
    what the backend actually said, not just that something went wrong.
    """

    def __init__(self, message: str, status_code: int, response_text: str):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class KafkaMLClient:
    """A thin, typed-ish wrapper around the Kafka-ML backend REST API.

    Args:
        base_url: e.g. ``"http://localhost:8000"``.
        timeout: per-request timeout in seconds, passed to `httpx.Client`.

    Can be used as a context manager (``with KafkaMLClient(...) as c:``) to
    close the underlying HTTP connection pool automatically; otherwise
    call `.close()` yourself when done.
    """

    def __init__(self, base_url: str, timeout: float = 30):
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "KafkaMLClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- internal ----------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = self._http.request(method, path, **kwargs)
        if resp.status_code >= 400:
            raise KafkaMLError(
                f"{method} {path} failed: {resp.status_code} {resp.text}",
                status_code=resp.status_code,
                response_text=resp.text,
            )
        return resp

    # -- models --------------------------------------------------------

    def create_model(
        self,
        name: str,
        code: str,
        framework: str = "tf",
        imports: str = "",
        description: str = "",
        distributed: bool = False,
        father: int | None = None,
    ) -> int:
        """Creates an ML model. The submitted code is validated live by
        the matching (tf/pth) `mlcode_executor` service before it's
        persisted - a `KafkaMLError` (400) means the code didn't pass
        that check, not a transport problem.

        For a distributed model's *child* node, pass `father` as the
        parent node's model id. Returns the new model's id (there's no
        `Location` header or created-object body on this endpoint, so this
        looks the new model up by name right after creating it)."""
        payload: dict[str, Any] = {
            "name": name,
            "code": code,
            "framework": framework,
            "imports": imports,
            "description": description,
            "distributed": distributed,
        }
        if father is not None:
            payload["father"] = father
        self._request("POST", "/models/", json=payload)
        return self._find_id_by_name("/models/", name)

    def get_model(self, model_id: int) -> dict[str, Any]:
        return self._request("GET", f"/models/{model_id}").json()

    def list_models(self) -> list[dict[str, Any]]:
        return self._request("GET", "/models/").json()

    def delete_model(self, model_id: int) -> None:
        self._request("DELETE", f"/models/{model_id}")

    # -- configurations --------------------------------------------------

    def create_configuration(self, name: str, model_ids: list[int], description: str = "") -> int:
        """Creates a configuration from a list of model ids. For a
        distributed model, only the *root* (father-less) model's id is
        needed - the backend walks the father/child chain and pulls the
        rest in automatically."""
        self._request(
            "POST",
            "/configurations/",
            json={"name": name, "ml_models": model_ids, "description": description},
        )
        return self._find_id_by_name("/configurations/", name)

    def get_configuration(self, configuration_id: int) -> dict[str, Any]:
        return self._request("GET", f"/configurations/{configuration_id}").json()

    def list_configurations(self) -> list[dict[str, Any]]:
        return self._request("GET", "/configurations/").json()

    def delete_configuration(self, configuration_id: int) -> None:
        self._request("DELETE", f"/configurations/{configuration_id}")

    # -- deployments -----------------------------------------------------

    def create_deployment(self, configuration: int, batch: int = 1, **fields) -> int:
        """Creates a deployment - this is the call that makes the backend
        submit one real Kubernetes training Job per (root) model in the
        configuration. `fields` is passed straight through to the API, so
        it can include any of: `tf_kwargs_fit`/`tf_kwargs_val` (TensorFlow,
        `"key=value, key2=value2"` strings - passed to `model.fit`/
        `.evaluate`), `pth_kwargs_fit`/`pth_kwargs_val` (PyTorch/ignite,
        same string format but different keys, e.g. `"max_epochs=1"`),
        `incremental`, `indefinite`, `stream_timeout`, `monitoring_metric`,
        `change`, `improvement` (incremental modes), `optimizer`,
        `learning_rate`, `loss`, `metrics` (distributed modes),
        `federated`, `agg_rounds`, `min_data`, `agg_strategy`,
        `data_restriction` (federated modes), `unsupervised`,
        `unsupervised_rounds`, `confidence`, `conf_mat_settings`, `gpumem`.

        Returns the new deployment's id."""
        before = {d["id"] for d in self.list_deployments()}
        self._request("POST", "/deployments/", json={"configuration": configuration, "batch": batch, **fields})
        after_ids = [d["id"] for d in self.list_deployments() if d["id"] not in before]
        if not after_ids:
            raise KafkaMLError("deployment created but no new id found in /deployments/", 0, "")
        return after_ids[-1]

    def list_deployments(self) -> list[dict[str, Any]]:
        return self._request("GET", "/deployments/").json()

    def delete_deployment(self, deployment_id: int) -> None:
        self._request("DELETE", f"/deployments/{deployment_id}")

    # -- results -----------------------------------------------------------

    def list_results(self, deployment_id: int | None = None) -> list[dict[str, Any]]:
        results = self._request("GET", "/results/").json()
        if deployment_id is not None:
            results = [r for r in results if r["deployment"]["id"] == deployment_id]
        return results

    def get_result(self, result_id: int) -> dict[str, Any]:
        results = self.list_results()
        for r in results:
            if r["id"] == result_id:
                return r
        raise KafkaMLError(f"result {result_id} not found", 404, "")

    def wait_for_results(
        self,
        deployment_id: int,
        status: str = "finished",
        timeout: float = 120,
        poll_interval: float = 2,
        min_results: int = 1,
    ) -> list[dict[str, Any]]:
        """Polls `/results/` until every `TrainingResult` for
        `deployment_id` reaches `status` (default: ``"finished"``), or
        raises `TimeoutError`. A distributed deployment produces one
        result per submodel - `min_results` should match that count."""
        deadline = time.monotonic() + timeout
        last_seen: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            rows = self.list_results(deployment_id)
            last_seen = rows
            if len(rows) >= min_results and all(r["status"] == status for r in rows):
                return rows
            time.sleep(poll_interval)
        raise TimeoutError(
            f"deployment {deployment_id} did not reach status={status!r} within {timeout}s - last seen: {last_seen}"
        )

    # -- inference -----------------------------------------------------

    def deploy_inference(
        self,
        result_id: int,
        input_topic: str,
        output_topic: str,
        input_format: str = "RAW",
        input_config: str = "",
        replicas: int = 1,
        **fields,
    ) -> int:
        """Deploys a trained result for real-time inference - creates a
        real Kubernetes `ReplicationController` (long-running, not a Job -
        remember to `stop_inference` + `delete_inference` when done).
        Returns the new inference's id."""
        before = {i["id"] for i in self.list_inferences()}
        self._request(
            "POST",
            f"/results/inference/{result_id}",
            json={
                "input_topic": input_topic,
                "output_topic": output_topic,
                "input_format": input_format,
                "input_config": input_config,
                "replicas": replicas,
                **fields,
            },
        )
        after_ids = [i["id"] for i in self.list_inferences() if i["id"] not in before]
        if not after_ids:
            raise KafkaMLError("inference created but no new id found in /inferences/", 0, "")
        return after_ids[-1]

    def list_inferences(self) -> list[dict[str, Any]]:
        return self._request("GET", "/inferences/").json()

    def stop_inference(self, inference_id: int) -> None:
        self._request("POST", f"/inferences/{inference_id}")

    def delete_inference(self, inference_id: int) -> None:
        self._request("DELETE", f"/inferences/{inference_id}")

    # -- datasets (needs the 'datasets' extra) --------------------------

    def send_dataset(
        self,
        bootstrap_servers: str,
        topic: str,
        deployment_id: int,
        data: Any,
        labels: Any,
        **kwargs,
    ) -> None:
        """Sends a numpy/pandas `data`/`labels` pair to Kafka and
        registers it as a datasource for `deployment_id` - see
        `kafkaml_client.datasets.send_dataset` for the full behavior and
        accepted `kwargs` (`description`, `validation_rate`, `test_rate`,
        `control_topic`, `group_id`). Needs the `datasets` extra (`pip
        install kafkaml-client[datasets]`); imported lazily here so
        constructing a plain `KafkaMLClient` never requires it."""
        from .datasets import send_dataset as _send_dataset

        _send_dataset(bootstrap_servers, topic, deployment_id, data, labels, **kwargs)

    def send_dataframe(
        self,
        bootstrap_servers: str,
        topic: str,
        deployment_id: int,
        dataframe: Any,
        label_column: str,
        **kwargs,
    ) -> None:
        """Sends a single pandas `DataFrame` (features + a `label_column`)
        to Kafka and registers it as a datasource for `deployment_id` -
        see `kafkaml_client.datasets.send_dataframe`. Needs the `datasets`
        extra, same as `send_dataset`."""
        from .datasets import send_dataframe as _send_dataframe

        _send_dataframe(bootstrap_servers, topic, deployment_id, dataframe, label_column, **kwargs)

    def predict_one(
        self,
        bootstrap_servers: str,
        input_topic: str,
        output_topic: str,
        row: Any,
        **kwargs,
    ) -> dict[str, Any]:
        """Sends one input row to a deployed real-time inference's input
        topic and returns the one prediction read back from its output
        topic - see `kafkaml_client.predictions.predict_one`. Needs the
        `datasets` extra, same as `send_dataset`."""
        from .predictions import predict_one as _predict_one

        return _predict_one(bootstrap_servers, input_topic, output_topic, row, **kwargs)

    def predict_batch(
        self,
        bootstrap_servers: str,
        input_topic: str,
        output_topic: str,
        rows: list[Any],
        **kwargs,
    ) -> list[dict[str, Any]]:
        """Sends every row in `rows` to a deployed real-time inference's
        input topic and returns the predictions read back from its output
        topic, in send order - see
        `kafkaml_client.predictions.predict_batch`. Needs the `datasets`
        extra, same as `send_dataset`."""
        from .predictions import predict_batch as _predict_batch

        return _predict_batch(bootstrap_servers, input_topic, output_topic, rows, **kwargs)

    # -- internal ----------------------------------------------------

    def _find_id_by_name(self, list_path: str, name: str) -> int:
        for row in self._request("GET", list_path).json():
            if row["name"] == name:
                return row["id"]
        raise KafkaMLError(f"{name!r} not found in {list_path} right after creating it", 0, "")
