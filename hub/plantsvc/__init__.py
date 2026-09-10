"""plantsvc - Plant Growth Monitoring hub service.

One FastAPI process serves the React dashboard, the camera-setup UI, the
capture/LED routine and the system status; `run_collector.py` stays a separate
process and remains the only writer of plant.db.
"""

__version__ = "2.0.0"
