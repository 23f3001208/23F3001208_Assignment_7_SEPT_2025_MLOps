from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import joblib
import pandas as pd
import logging
import time
import json

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

# Setup Tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(CloudTraceSpanExporter())
trace.get_tracer_provider().add_span_processor(span_processor)

# Setup structured logging
logger = logging.getLogger("iris-ml-service")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()

formatter = logging.Formatter(json.dumps({
    "severity": "%(levelname)s",
    "message": "%(message)s",
    "timestamp": "%(asctime)s"
}))
handler.setFormatter(formatter)
logger.addHandler(handler)

app = FastAPI(title="Iris Classifier API")

# App state for health checks
app_state = {"is_ready": False, "is_alive": True}

# Load model on startup
model = None

@app.on_event("startup")
async def startup_event():
    global model
    try:
        logger.info(json.dumps({"event": "startup", "message": "Loading model"}))
        time.sleep(2)  # Simulate model loading time
        model = joblib.load("model.joblib")
        app_state["is_ready"] = True
        logger.info(json.dumps({"event": "startup", "message": "Model loaded successfully"}))
    except Exception as e:
        logger.error(json.dumps({"event": "startup_error", "error": str(e)}))
        app_state["is_alive"] = False

# Health check endpoints
@app.get("/live_check", tags=["Probe"])
async def liveness_probe():
    if app_state["is_alive"]:
        return {"status": "alive"}
    return Response(status_code=500)

@app.get("/ready_check", tags=["Probe"])
async def readiness_probe():
    if app_state["is_ready"]:
        return {"status": "ready"}
    return Response(status_code=503)

# Middleware for request timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Process-Time-ms"] = str(duration)
    return response

# Exception handler
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    span = trace.get_current_span()
    trace_id = format(span.get_span_context().trace_id, "032x")
    logger.exception(json.dumps({
        "event": "unhandled_exception",
        "trace_id": trace_id,
        "path": str(request.url),
        "error": str(exc)
    }))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "trace_id": trace_id},
    )

# Input schema
class IrisInput(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

@app.get("/")
def read_root():
    return {"message": "Welcome to the Iris Classifier API!"}

@app.post("/predict")
async def predict_species(data: IrisInput, request: Request):
    with tracer.start_as_current_span("iris_prediction") as span:
        start_time = time.time()
        trace_id = format(span.get_span_context().trace_id, "032x")

        try:
            input_df = pd.DataFrame([data.dict()])
            prediction = model.predict(input_df)[0]
            latency = round((time.time() - start_time) * 1000, 2)

            logger.info(json.dumps({
                "event": "prediction",
                "trace_id": trace_id,
                "input": data.dict(),
                "result": {"predicted_class": prediction},
                "latency_ms": latency,
                "status": "success"
            }))

            return {
                "predicted_class": prediction,
                "latency_ms": latency,
                "trace_id": trace_id
            }

        except Exception as e:
            logger.exception(json.dumps({
                "event": "prediction_error",
                "trace_id": trace_id,
                "error": str(e)
            }))
            raise HTTPException(status_code=500, detail="Prediction failed")

@app.post("/predict/")
async def predict_species_legacy(data: IrisInput, request: Request):
    """Legacy endpoint for backward compatibility"""
    return await predict_species(data, request)
