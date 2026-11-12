import argparse
import asyncio
import itertools
from collections import Counter
from typing import Any

from aiohttp import web
from dotenv import load_dotenv
from river import compose, drift, linear_model, naive_bayes, preprocessing, tree

from system_monitor import get_system_usage
from db_logging import log_cpu_mem, log_bot_stats

load_dotenv()

DEFAULT_CPU = 10.0
DEFAULT_MEMORY = 30.0

stats_lock = asyncio.Lock()
seen_users: set[Any] = set()
blocked_users: set[Any] = set()

system_state = {
    "MARKET": {"cpu": DEFAULT_CPU, "mem": DEFAULT_MEMORY},
    "TRADE": {"cpu": DEFAULT_CPU, "mem": DEFAULT_MEMORY},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the online-learning bot guard."
    )
    parser.add_argument(
        "--classifier",
        choices=("logistic-regression", "gaussian-nb", "hoeffding-tree"),
        default="logistic-regression",
        help="River classifier used by the guard (default: logistic-regression).",
    )
    parser.add_argument(
        "--drift-detection",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable or disable DDM-based drift retraining (default: disabled).",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


def build_classifier(name: str, use_drift_detection: bool):
    if name == "logistic-regression":
        base_model = compose.Pipeline(
            preprocessing.StandardScaler(),
            linear_model.LogisticRegression(),
        )
    elif name == "gaussian-nb":
        base_model = naive_bayes.GaussianNB()
    elif name == "hoeffding-tree":
        base_model = tree.HoeffdingTreeClassifier()
    else:
        raise ValueError(f"Unsupported classifier: {name}")

    if not use_drift_detection:
        return base_model

    return drift.DriftRetrainingClassifier(
        model=base_model,
        drift_detector=drift.binary.DDM(),
        train_in_background=True,
    )


def label_from_persona(user_persona: str) -> bool:
    return "SCRAPER_BOT" in user_persona.upper()


def update_system_state(data: dict[str, Any]) -> None:
    incoming_cpu = float(data.get("cpuUsage") or 0.0)
    incoming_mem = float(data.get("memoryUsage") or 0.0)
    service_type = str(data.get("serviceType", "MARKET")).upper()

    if incoming_cpu <= 0:
        try:
            incoming_cpu, _ = get_system_usage()
        except Exception:
            incoming_cpu = DEFAULT_CPU

    if service_type in system_state:
        system_state[service_type]["cpu"] = incoming_cpu
        system_state[service_type]["mem"] = incoming_mem


def build_features(
    data: dict[str, Any], url_counts: Counter, observed_urls: int
) -> dict[str, float]:
    update_system_state(data)
    raw_url = str(data.get("endpointUrl", ""))
    raw_method = str(data.get("apiMethod", "")).upper()
    endpoint_frequency = (url_counts[raw_url] / observed_urls) if observed_urls else 0.0
    return {
        "apiTime": float(data.get("apiTime") or 0.0),
        "applicationTime": float(data.get("applicationTime") or 0.0),
        "databaseTime": float(data.get("databaseTime") or 0.0),
        "cpuUsage_market": system_state["MARKET"]["cpu"],
        "cpuUsage_trade": system_state["TRADE"]["cpu"],
        "memoryUsage_trade": system_state["TRADE"]["mem"],
        "memoryUsage_market": system_state["MARKET"]["mem"],
        "endpointUrl": endpoint_frequency,
        "apiMethod": 1.0 if raw_method == "POST" else 0.0,
    }


async def update_block_stats(user_id: Any, is_bot: bool) -> None:
    if user_id is None:
        return

    async with stats_lock:
        seen_users.add(user_id)
        is_newly_blocked = is_bot and user_id not in blocked_users
        if is_newly_blocked:
            blocked_users.add(user_id)
            total = len(seen_users)
            blocked = len(blocked_users)
            active = total - blocked
            try:
                log_bot_stats(total, blocked, active)
                print(
                    f"[DB SAVED] New block! User: {user_id}. "
                    f"Stats: {blocked}/{total}"
                )
            except Exception as exc:
                print(f"Failed to log bot stats: {exc}")


async def model_worker(app: web.Application) -> None:
    queue: asyncio.Queue = app["model_queue"]
    model = app["model"]
    url_counts: Counter = app["url_counts"]

    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break

        sequence_id, data, result_future = item
        try:
            user_persona = data.get("userPersona")
            if not isinstance(user_persona, str) or not user_persona.strip():
                raise ValueError("userPersona is required for online learning")

            raw_url = str(data.get("endpointUrl", ""))
            x = build_features(data, url_counts, app["observed_urls"])
            y = label_from_persona(user_persona)

            # Prequential order: transform and predict using only past state,
            # then update the model and the online endpoint-frequency state.
            prediction = model.predict_one(x)
            is_bot = bool(prediction) if prediction is not None else False
            model.learn_one(x, y)
            url_counts[raw_url] += 1
            app["observed_urls"] += 1

            await update_block_stats(data.get("userId"), is_bot)

            if is_bot:
                print(
                    f"[BLOCK] Sequence: {sequence_id} | "
                    f"Request: {data.get('requestId')} | "
                    f"User: {data.get('userId')} | Prediction: {prediction}"
                )

            if not result_future.cancelled():
                result_future.set_result(
                    {
                        "sequence_id": sequence_id,
                        "is_bot": is_bot,
                        "prediction": prediction,
                    }
                )
        except Exception as exc:
            if not result_future.cancelled():
                result_future.set_exception(exc)
        finally:
            queue.task_done()


async def predict(request: web.Request) -> web.Response:
    data = await request.json()
    sequence_id = next(request.app["sequence"])
    loop = asyncio.get_running_loop()
    result_future = loop.create_future()

    await request.app["model_queue"].put((sequence_id, data, result_future))

    try:
        result = await result_future
    except ValueError as exc:
        raise web.HTTPUnprocessableEntity(text=str(exc)) from exc

    return web.json_response(result)


async def monitor_system(app: web.Application) -> None:
    try:
        while True:
            try:
                cpu, mem = get_system_usage()
                log_cpu_mem(cpu, mem)
            except Exception as exc:
                print(f"System monitoring error: {exc}")
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        print("System monitoring stopped.")
        raise


async def start_background_tasks(app: web.Application) -> None:
    app["model_worker_task"] = asyncio.create_task(model_worker(app))
    app["monitor_task"] = asyncio.create_task(monitor_system(app))


async def cleanup_background_tasks(app: web.Application) -> None:
    await app["model_queue"].put(None)
    await app["model_worker_task"]

    app["monitor_task"].cancel()
    try:
        await app["monitor_task"]
    except asyncio.CancelledError:
        pass


def create_app(args: argparse.Namespace) -> web.Application:
    app = web.Application()
    app["model"] = build_classifier(
        args.classifier,
        args.drift_detection,
    )
    app["model_queue"] = asyncio.Queue()
    app["sequence"] = itertools.count(1)
    app["url_counts"] = Counter()
    app["observed_urls"] = 0
    app.add_routes([web.post("/predict", predict)])
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app


if __name__ == "__main__":
    cli_args = parse_args()
    print(
        "Starting bot guard with "
        f"classifier={cli_args.classifier}, "
        f"drift_detection={cli_args.drift_detection}"
    )
    web.run_app(create_app(cli_args), host=cli_args.host, port=cli_args.port)
