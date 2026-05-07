from fastapi import APIRouter, HTTPException, status

from ..models.signal import BatchSignalIngestion, SignalIngestion, SignalResponse
from ..services.ingestion_service import ingestion_service

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.post("", response_model=SignalResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_signal(signal: SignalIngestion):
    """
    Ingest a single signal. Processing is fully async — the caller receives
    202 Accepted immediately. Returns 503 when the queue is at capacity
    (backpressure signal to the upstream producer).
    """
    payload = signal.model_dump()
    if signal.timestamp:
        payload["timestamp"] = signal.timestamp.isoformat()

    signal_id, queued = await ingestion_service.enqueue(payload)
    if not queued:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "System under heavy load — signal queue at capacity.",
                "queue_depth": ingestion_service.queue_depth(),
                "retry_after_ms": 1000,
            },
        )

    return SignalResponse(
        signal_id=signal_id,
        work_item_id="pending",
        status="queued",
        message="Signal accepted for async processing",
    )


@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(batch: BatchSignalIngestion):
    """Batch ingestion for high-throughput producers."""
    if ingestion_service.is_queue_full():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System under load — retry later.",
        )

    results = []
    for signal in batch.signals:
        payload = signal.model_dump()
        if signal.timestamp:
            payload["timestamp"] = signal.timestamp.isoformat()
        signal_id, queued = await ingestion_service.enqueue(payload)
        results.append({"signal_id": signal_id, "queued": queued})

    accepted = sum(1 for r in results if r["queued"])
    return {"total": len(results), "accepted": accepted, "results": results}
