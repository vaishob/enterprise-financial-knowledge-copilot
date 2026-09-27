import json
import logging
from contextlib import contextmanager
from time import perf_counter

from opentelemetry import metrics, trace

audit_logger = logging.getLogger("copilot.audit")
tracer = trace.get_tracer("financial-copilot", "0.1.0")
meter = metrics.get_meter("financial-copilot", "0.1.0")
request_counter = meter.create_counter("copilot.requests")
abstention_counter = meter.create_counter("copilot.abstentions")
model_counter = meter.create_counter("copilot.model_invocations")
retrieval_counter = meter.create_counter("copilot.retrievals")
exception_counter = meter.create_counter("copilot.exceptions")
latency_histogram = meter.create_histogram("copilot.request.duration", unit="ms")


def setup_telemetry(settings):
    # Persisted audit records are also emitted as one JSON object per log line.
    audit_logger.setLevel(logging.INFO)
    if not audit_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit_logger.addHandler(handler)
    if not settings.telemetry_enabled:
        return
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_endpoint)))
    trace.set_tracer_provider(provider)
    metrics_endpoint = settings.otel_endpoint.removesuffix("/v1/traces") + "/v1/metrics"
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=metrics_endpoint))
    metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))


@contextmanager
def stage(timings: dict, name: str):
    start = perf_counter()
    with tracer.start_as_current_span(name, record_exception=False, set_status_on_exception=False):
        try:
            yield
        finally:
            timings[name + "_ms"] = round((perf_counter() - start) * 1000, 3)


def emit_audit(payload: dict):
    # Never serialize query, retrieved bodies, provider exception strings, credentials or reasoning.
    audit_logger.info(json.dumps(payload, separators=(",", ":")))
