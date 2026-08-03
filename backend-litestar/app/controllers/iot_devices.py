import asyncio
import json
import logging
import os
import time
from typing import Any

import anyio
import httpx
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from litestar import Request, Router, get, post, put, delete
from litestar.exceptions import HTTPException
from litestar.response import File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import IoTDevice, TrainingResult
from app.schemas import iot_device_dict

logger = logging.getLogger(__name__)


def generate_device_backlog_config(device: dict[str, Any]) -> str:
    return (
        f'Backlog DeviceName {device["token"]}; FriendlyName {device["friendly_name"]}; '
        f'MqttHost {device["mqtt_address"]}; MqttPort {device["mqtt_port"]}; '
        f'MqttUser {device["mqtt_username"]}; MqttPassword {device["mqtt_password"]}; '
        f'Topic {device["token"]}; FullTopic kafkaml/iot/%topic%/%prefix%/ ; '
        f'MqttClient {device["token"]}; Hostname {device["token"]}; SetOption53 1 '
    )


def generate_download_berry_script(url: str, device: IoTDevice) -> str:
    berry_script = f"""
    def urlfetch(url,file);
        if file==nil;
            import string;
            file=string.split(url,'/').pop();
        end; var wc=webclient();
        wc.begin(url);
        var st=wc.GET();
        if st!=200
            st = 'connection_error';
            print('status: '+str(st));
        end;
        st='Fetched '+str(wc.write_file(file));
        print(url,st); wc.close();
        return st;
    end;
    tasmota.cmd('UfsDelete autoexec.be');
    tasmota.cmd('UfsDelete model.tflite');
    urlfetch('{url}/api/iot-devices/{device.token}/autoexec.be');
    urlfetch('{url}/api/iot-devices/{device.token}/model.tflite');
    tasmota.cmd('Restart 1');
    """
    return " ".join(
        line.strip()
        for line in berry_script.strip().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def _check_device_status(device: dict[str, Any]) -> tuple[int, str]:
    """Synchronous MQTT round-trip (paho-mqtt has no asyncio API); run this
    inside a worker thread (see `_device_status_async`) so it doesn't block
    the event loop while it waits up to ~0.5s per device."""
    status_received = {"status": "disconnected"}

    try:
        client = mqtt.Client()

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                client.subscribe(f"kafkaml/iot/{device['token']}/stat/STATUS1")
                client.publish(f"kafkaml/iot/{device['token']}/cmnd/Status", "1")

        def on_message(client, userdata, message):
            if message.topic == f"kafkaml/iot/{device['token']}/stat/STATUS1":
                status_received["status"] = "connected"
            client.disconnect()

        client.on_connect = on_connect
        client.on_message = on_message

        client.username_pw_set(device["mqtt_username"], device["mqtt_password"])
        client.connect(device["mqtt_address"], device["mqtt_port"], 60)

        client.loop_start()
        time.sleep(0.5)
        client.loop_stop()
    except Exception as e:
        logger.error(f"[{device['token']}] MQTT error: {e}")

    return device["id"], status_received["status"]


async def _device_status_async(device: dict[str, Any]) -> tuple[int, str]:
    return await anyio.to_thread.run_sync(_check_device_status, device)


def send_mqtt_message_to_tasmota(device: IoTDevice, cmnd: str, payload: str) -> None:
    topic = f"kafkaml/iot/{device.token}/cmnd/{cmnd}"
    try:
        publish.single(
            topic=topic,
            payload=payload,
            hostname=device.mqtt_address,
            port=device.mqtt_port,
            auth={"username": device.mqtt_username, "password": device.mqtt_password},
            qos=1,
            retain=False,
        )
    except Exception as e:
        logger.error(f"Failed to send MQTT message to device {device.token}: {e}")


@get("/iot-devices/", tags=["iot-devices"])
async def list_iot_devices(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(select(IoTDevice).order_by(IoTDevice.friendly_name))
    devices = [iot_device_dict(d) for d in result.scalars().all()]

    # Concurrent (not blocking the event loop) MQTT status probe per device -
    # the async-native equivalent of the original's ThreadPoolExecutor(10).
    statuses = await asyncio.gather(*(_device_status_async(d) for d in devices))
    status_by_id = dict(statuses)

    for device in devices:
        device["status"] = status_by_id.get(device["id"], "disconnected")
        device["backlog"] = generate_device_backlog_config(device)

    return devices


@post("/iot-devices/", tags=["iot-devices"])
async def create_iot_device(data: dict[str, Any], db_session: AsyncSession) -> None:
    device = IoTDevice(
        friendly_name=data["friendly_name"],
        mqtt_address=data["mqtt_address"],
        mqtt_port=data["mqtt_port"],
        mqtt_username=data["mqtt_username"],
        mqtt_password=data["mqtt_password"],
    )
    db_session.add(device)
    await db_session.flush()

    os.makedirs(settings.DEVICES_ROOT / device.token, exist_ok=True)


@get("/iot-devices/{device_id:int}", tags=["iot-devices"])
async def get_iot_device(device_id: int, db_session: AsyncSession) -> dict[str, Any]:
    device = await db_session.get(IoTDevice, device_id)
    if device is None:
        raise HTTPException(status_code=400, detail="Device does not exist")
    return iot_device_dict(device)


@put("/iot-devices/{device_id:int}", tags=["iot-devices"])
async def update_iot_device(device_id: int, data: dict[str, Any], db_session: AsyncSession) -> None:
    device = await db_session.get(IoTDevice, device_id)
    if device is None:
        raise HTTPException(status_code=400, detail="Device does not exist")

    device.friendly_name = data.get("friendly_name", device.friendly_name)
    device.mqtt_address = data.get("mqtt_address", device.mqtt_address)
    device.mqtt_port = data.get("mqtt_port", device.mqtt_port)
    device.mqtt_username = data.get("mqtt_username", device.mqtt_username)
    device.mqtt_password = data.get("mqtt_password", device.mqtt_password)


@delete("/iot-devices/{device_id:int}", tags=["iot-devices"], status_code=200)
async def delete_iot_device(device_id: int, db_session: AsyncSession) -> None:
    device = await db_session.get(IoTDevice, device_id)
    if device is None:
        raise HTTPException(status_code=400, detail="Device does not exist")
    await db_session.delete(device)


@get("/iot-devices/{token:str}/model.tflite", tags=["iot-devices"])
async def download_iot_model(token: str, db_session: AsyncSession) -> File:
    device = (
        await db_session.execute(select(IoTDevice).where(IoTDevice.token == token))
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    path = settings.DEVICES_ROOT / device.token / "model.tflite"
    return File(path=path, filename="model.tflite", media_type="application/octet-stream")


@get("/iot-devices/{token:str}/autoexec.be", tags=["iot-devices"])
async def download_iot_script(token: str, db_session: AsyncSession) -> File:
    device = (
        await db_session.execute(select(IoTDevice).where(IoTDevice.token == token))
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    path = settings.DEVICES_ROOT / device.token / "autoexec.be"
    return File(path=path, filename="autoexec.be", media_type="application/octet-stream")


@post("/results/inference-iot/{result_id:int}", tags=["iot-devices"], status_code=200)
async def deploy_to_iot_devices(
    result_id: int,
    data: dict[str, Any],
    db_session: AsyncSession,
    http_client: httpx.AsyncClient,
    request: Request,
) -> None:
    berry_script: str | None = data.get("code")
    device_tokens: list[str] = data.get("device_token", [])
    apply_int_quant: bool = data.get("applyIntQuant", False)

    if not berry_script or not device_tokens:
        raise HTTPException(
            status_code=400, detail="Missing required fields: 'code' or 'device_token'."
        )

    training_result = await db_session.get(TrainingResult, result_id)
    if training_result is None:
        raise HTTPException(status_code=404, detail="Model result not found.")

    devices = (
        await db_session.execute(select(IoTDevice).where(IoTDevice.token.in_(device_tokens)))
    ).scalars().all()
    if not devices:
        raise HTTPException(status_code=404, detail="No valid devices found.")

    tflite_parser_config = {
        "applyQuantization": apply_int_quant,
        "quantizationType": "int8" if apply_int_quant else "",
        "modelDeploymentId": training_result.deployment_id if apply_int_quant else "",
        "dataControlTopic": settings.CONTROL_TOPIC if apply_int_quant else "",
        "dataBootstrapServers": settings.BOOTSTRAP_SERVERS if apply_int_quant else "",
    }

    model_path = settings.MEDIA_ROOT / settings.TRAINED_MODELS_DIR / f"{result_id}.h5"
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model file not found.")

    try:
        resp = await http_client.post(
            settings.TENSORFLOW_EXECUTOR_URL + "convert_to_tflite/",
            files={f"{result_id}.h5": model_path.read_bytes()},
            data=tflite_parser_config,
            timeout=30,
        )
    except httpx.HTTPError as e:
        logger.error(f"TensorFlow executor error: {e}")
        raise HTTPException(status_code=503, detail="Error contacting model conversion service.") from e

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Model conversion failed.")

    tflite_dir = settings.MEDIA_ROOT / settings.TFLITE_PARSED_MODELS_DIR
    tflite_dir.mkdir(parents=True, exist_ok=True)
    (tflite_dir / f"{result_id}.tflite").write_bytes(resp.content)

    frontend_url = request.headers.get("Origin", settings.FRONTEND_URL)

    for device in devices:
        device_path = settings.DEVICES_ROOT / device.token
        device_path.mkdir(parents=True, exist_ok=True)

        (device_path / "model.tflite").write_bytes(resp.content)
        (device_path / "autoexec.be").write_bytes(berry_script.encode("utf-8"))

        device_script = generate_download_berry_script(frontend_url, device)
        await anyio.to_thread.run_sync(send_mqtt_message_to_tasmota, device, "Br", device_script)


router = Router(
    path="/",
    route_handlers=[
        list_iot_devices,
        create_iot_device,
        get_iot_device,
        update_iot_device,
        delete_iot_device,
        download_iot_model,
        download_iot_script,
        deploy_to_iot_devices,
    ],
)
