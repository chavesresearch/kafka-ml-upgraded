import ast
import json

from kubernetes_asyncio import client

from app.config import settings


def is_blank(attribute: str | None) -> bool:
    """Checks if the attribute is an empty string or None."""
    return attribute is None or attribute == ""


def kubernetes_api_client(token: str | None = None, external_host: str | None = None) -> client.ApiClient:
    """Builds a Kubernetes API client.

    You can provide a token and the external host IP to access an external
    Kubernetes cluster. If one of them is not provided, the configuration
    returned targets the local/in-cluster machine (set up by
    ``kubernetes_asyncio.config.load_incluster_config`` beforehand).
    """
    if token is not None and external_host is not None:
        configuration = client.Configuration()
        configuration.host = external_host
        configuration.verify_ssl = False
        configuration.api_key = {"authorization": "Bearer " + token}
        return client.ApiClient(configuration)

    # Real bug, found via an actual in-cluster Job-creation attempt (not
    # by inspection - see federated-module/CLAUDE.md, where this
    # exact same bug was found in federated_backend's byte-identical
    # `kubernetes_config()` helper): `client.Configuration()`'s bare
    # constructor does *not* inherit whatever
    # `config.load_incluster_config()` registered as the process-wide
    # default - it hardcodes `self._base_path = "http://localhost"`
    # unconditionally when no `host` kwarg is given (confirmed by reading
    # `Configuration.__init__`'s actual source). Building a fresh blank
    # `Configuration()` here and handing it to `ApiClient` discarded the
    # in-cluster host/cert entirely, so every in-cluster (no
    # token/external_host) call would fail with `ApiException`/connection
    # errors targeting `http://localhost`, on any library version.
    # `ApiClient()` with *no* Configuration argument does the right thing
    # instead - it resolves `Configuration.get_default_copy()` internally,
    # which *does* pick up `load_incluster_config()`'s result.
    return client.ApiClient()


def parse_kwargs_fit(kwargs_fit: str | None) -> str:
    """Converts a ``key=value, key2=value2`` string into a JSON object string.

    Example:
        "epochs=5, steps_per_epoch=1000" -> '{"epochs": 5, "steps_per_epoch": 1000}'
    """
    dic = {}
    if kwargs_fit is not None and kwargs_fit != "":
        kwargs_fit = kwargs_fit.replace(" ", "")
        for param in kwargs_fit.split(","):
            pair = param.split("=")
            # ast.literal_eval, not eval() - this runs in the backend API
            # pod itself (unlike model code, which is always exec()'d in an
            # isolated, non-root mlcode_executor subprocess), on a
            # user-submitted string, so it must not be able to execute
            # arbitrary code. literal_eval only ever produces a literal
            # (int/float/str/bool/None/list/tuple/dict) - every real
            # kwargs_fit value (epochs=5, verbose=True, ...) is exactly
            # that, never an expression that needs full eval().
            dic[pair[0]] = ast.literal_eval(pair[1])

    return json.dumps(dic)


async def delete_replication_controller(
    inference_id: int, token: str | None = None, external_host: str | None = None
) -> None:
    """Deletes a previously deployed inference ReplicationController.

    You can also provide an external host and its token to delete a
    deployment there. If one of them is not provided, this deletes locally
    (in-cluster).
    """
    api_client = kubernetes_api_client(token=token, external_host=external_host)
    async with api_client:
        api_instance = client.CoreV1Api(api_client)
        await api_instance.delete_namespaced_replication_controller(
            name="model-inference-" + str(inference_id),
            namespace=settings.KUBE_NAMESPACE,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
