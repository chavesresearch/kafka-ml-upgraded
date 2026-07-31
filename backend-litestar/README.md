# Back-end (Litestar)

This is a from-scratch port of `backend/` (the Django/DRF backend) to [Litestar](https://litestar.dev/), Litestar's async-native successor stack. It exposes the exact same URL contract the Angular frontend already speaks (`/models/`, `/configurations/`, `/deployments/`, `/results/`, `/inferences/`, `/datasources/`, `/iot-devices/`, `/ws/`), so it's a drop-in replacement - no frontend changes required.

Stack:
- **[Litestar](https://litestar.dev/)** instead of Django+DRF - async request handlers throughout.
- **SQLAlchemy 2.0 (async) + `aiosqlite`** instead of the Django ORM, same single-file local SQLite database (`db.sqlite3`).
- **Alembic** instead of `manage.py makemigrations`/`migrate`.
- **`aiokafka`** instead of `confluent-kafka` for the datasource producer and the `/ws/` Kafka-to-websocket relay.
- **`kubernetes-asyncio`** instead of the sync `kubernetes` client for Job/ReplicationController management.
- **`httpx.AsyncClient`** instead of `requests` for calling the tf/pth `mlcode_executor` services.
- Native Litestar `WebSocket` support instead of Django Channels (no channel layer needed - the relay is a plain `asyncio.Task` per subscription).

A brief introduction of the important files:
- `app/models.py` - SQLAlchemy models (equivalent of `automl/models.py`).
- `app/controllers/*.py` - route handlers, one module per resource (equivalent of `automl/views/*.py`).
- `app/schemas/__init__.py` - response dict builders, field-for-field equivalents of `automl/serializers.py`.
- `app/websocket.py` - the `/ws/` Kafka visualization relay (equivalent of `automl/websockets.py`).
- `app/job_manifest_generator.py` - Kubernetes Job manifest builders, ported unchanged (it never depended on Django).
- `app/config.py` - environment-driven settings (equivalent of `autoweb/settings.py`).
- `app/main.py` - app wiring: routes, CORS, DI, startup/shutdown lifecycle.

## Installation for local development

```
python -m pip install -r requirements.txt
```

Then create the local SQLite database:

```
alembic upgrade head
```

This creates `db.sqlite3` in this directory, same as before. After changing `app/models.py`, generate a new migration instead of hand-editing the schema:

```
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Running development server

```
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --ws wsproto
```

`--ws wsproto` is required: `web3` (the optional blockchain feature) pins `websockets<10`, so `wsproto` is used as uvicorn's websocket implementation instead of the `websockets` package. See the comment in `requirements.txt`.

If you change the IP or port, also update `frontend/src/environments/environment.ts`.

For local (non-in-cluster) Kubernetes access, swap the config call the same way the old backend's README described - `app/controllers/deployments.py` and `app/controllers/inferences.py` call `k8s_config.load_incluster_config()`; swap to `k8s_config.load_kube_config()` to run outside a container.

There is no Django-admin equivalent shipped here - the original admin site was registered but unused by the frontend (nothing links to `/admin`), so it wasn't ported. Say if you'd like a minimal read-only admin view added back.

## Environment variables

Same names as before, read directly from the environment (see `app/config.py`):
`BOOTSTRAP_SERVERS`, `CONTROL_TOPIC`, `KUBE_NAMESPACE`, `KUBE_TOKEN`, `KUBE_HOST`, `TENSORFLOW_TRAINING_MODEL_IMAGE`, `TENSORFLOW_INFERENCE_MODEL_IMAGE`, `PYTORCH_TRAINING_MODEL_IMAGE`, `PYTORCH_INFERENCE_MODEL_IMAGE`, `FRONTEND_URL`, `BACKEND_URL`, `TFEXECUTOR_URL`, `PTHEXECUTOR_URL`, `ALLOWED_HOSTS`, `DEBUG`, `MODEL_LOGGER_TOPIC`, `ENABLE_FEDML_BLOCKCHAIN` and the `FEDML_BLOCKCHAIN_*` variables.

Two new variables, both with sane defaults, cover settings the original backend referenced but never actually defined (see the fixes note below): `DEVICES_ROOT` (defaults to `<this dir>/models/devices`) and nothing else needs configuring for `TFLITE_PARSED_MODELS_DIR` (defaults to `tflite/`, relative to `MEDIA_ROOT`).

## Behavioral notes vs. the Django backend

A few things were fixed rather than ported as-is - see the accompanying chat summary for the full list, but in short:
- `settings.DEVICES_ROOT` / `TFLITE_PARSED_MODELS_DIR` were referenced by IoT device code but never defined, so creating a device or deploying to one crashed. Now defined.
- `GET /models/result/{id}` was dead code (a duplicate method definition silently shadowed the real implementation), returning the wrong JSON shape. Fixed.
- `Datasource` rows were validated but never persisted. Now persisted.
- The Kafka control-topic message key was capped at 255 (`bytes([deployment_id])`); widened to 4 bytes.
- The Kafka producer and Kubernetes client now connect lazily, so the pod doesn't fail to boot if Kafka/K8s aren't reachable yet at startup.
