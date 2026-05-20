"""Historical race streamer.

The streamer pretends to be a real time telemetry source. In practice it pulls
a real historical Formula session through FastF1, merges car physics with
positional data, and replays the session frame by frame at a configurable
speed. Every frame is pushed into the raw telemetry topic so the rest of the
pipeline behaves as if the race were happening right now.
"""

from __future__ import annotations

import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Dict, List

import fastf1
import numpy as np
import pandas as pd

from src.backend.config import get_settings
from src.backend.ingestion.kafka_producer import NeuroPitKafkaProducer
from src.backend.ingestion.models import TelemetryFrame

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "fastf1_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)


class HistoricalRaceStreamer:
    """Plays back a real F1 session as if it were a live telemetry feed."""

    def __init__(
        self,
        year: int,
        event: str,
        session: str,
        drivers: List[str],
        playback_speed: float = 1.0,
    ):
        self.year = year
        self.event = event
        self.session_name = session
        self.drivers = drivers
        self.playback_speed = playback_speed
        self.producer = NeuroPitKafkaProducer()
        self.race_session = None
        self.telemetry_data: Dict[str, pd.DataFrame] = {}

    def load_data(self) -> None:
        logger.info("Loading session %s %s %s", self.year, self.event, self.session_name)
        self.race_session = fastf1.get_session(self.year, self.event, self.session_name)
        self.race_session.load()

        for driver in self.drivers:
            logger.info("Loading telemetry for driver %s", driver)
            laps = self.race_session.laps.pick_driver(driver)

            car_data = laps.get_car_data().add_distance()
            pos_data = laps.get_pos_data()

            merged = pd.merge_asof(
                car_data.sort_values("Time"),
                pos_data.sort_values("Time"),
                on="Time",
                direction="nearest",
            )
            merged = merged.dropna(subset=["Speed", "Throttle", "Brake"])
            merged = self._enrich_with_steering(merged)
            self.telemetry_data[driver] = merged
            logger.info("Loaded %d telemetry frames for %s", len(merged), driver)

    @staticmethod
    def _enrich_with_steering(frames: pd.DataFrame) -> pd.DataFrame:
        """Derive a steering angle proxy from the position trace.

        FastF1 does not surface a true steering wheel angle, so we infer
        the driver's input from how sharply the car is turning. We take
        the heading at each sample from successive (X, Y) points, then
        compute the change in heading per timestep and scale it into a
        plausible degree range. The proxy is honest about what it is
        and labelled the same way downstream consumers treat any other
        derived signal.
        """
        if frames.empty or {"X", "Y"}.difference(frames.columns):
            frames = frames.copy()
            frames["steering_angle"] = 0.0
            return frames

        x = frames["X"].to_numpy(dtype=float)
        y = frames["Y"].to_numpy(dtype=float)
        dx = np.diff(x, prepend=x[0])
        dy = np.diff(y, prepend=y[0])
        heading = np.arctan2(dy, dx)
        delta = np.diff(heading, prepend=heading[0])
        # Wrap into [-pi, pi].
        delta = (delta + math.pi) % (2 * math.pi) - math.pi
        # Convert to degrees and scale. Empirically the per-sample delta
        # rarely exceeds 0.25 rad, so multiplying by 180/pi gives a band
        # around plus/minus 14 degrees, which we then amplify into the
        # plus/minus 180 degree wheel angle range.
        steering_deg = np.degrees(delta) * 12.0
        steering_deg = np.clip(steering_deg, -180.0, 180.0)
        frames = frames.copy()
        frames["steering_angle"] = steering_deg
        return frames

    def execute_playback(self) -> None:
        if not self.telemetry_data:
            logger.error("No telemetry data loaded. Run load_data() first.")
            return

        logger.info("Starting temporal playback at %.2fx speed", self.playback_speed)

        master_frames = []
        for driver, df in self.telemetry_data.items():
            for _, row in df.iterrows():
                master_frames.append(
                    {
                        "driver": driver,
                        "offset_sec": row["Time"].total_seconds(),
                        "row": row,
                    }
                )

        master_frames.sort(key=lambda x: x["offset_sec"])
        logger.info("Prepared %d interleaved frames", len(master_frames))

        session_identifier = f"{self.year}_{self.event.replace(' ', '')}"

        simulated_start_time = time.time()
        first_frame_offset = master_frames[0]["offset_sec"]

        try:
            for idx, item in enumerate(master_frames):
                row = item["row"]
                driver = item["driver"]
                offset = item["offset_sec"]

                target_sim_time = simulated_start_time + (
                    (offset - first_frame_offset) / self.playback_speed
                )
                sleep_duration = target_sim_time - time.time()
                if sleep_duration > 0:
                    time.sleep(sleep_duration)

                frame = TelemetryFrame(
                    timestamp=datetime.now(timezone.utc),
                    driver_id=driver,
                    session_id=session_identifier,
                    speed=float(row.get("Speed", 0.0)),
                    rpm=int(row.get("RPM", 0)),
                    gear=int(row.get("Gear", 0)),
                    throttle=float(row.get("Throttle", 0.0)),
                    brake=float(row.get("Brake", 0.0)),
                    steering_angle=float(row.get("steering_angle", 0.0)),
                    drs=int(row.get("DRS", 0)),
                    x=float(row.get("X", 0.0)),
                    y=float(row.get("Y", 0.0)),
                    z=float(row.get("Z", 0.0)),
                    status="OnTrack",
                )

                self.producer.produce_telemetry(frame)

                if idx % 1000 == 0:
                    logger.info("Streamed %d/%d frames", idx, len(master_frames))

        except KeyboardInterrupt:
            logger.info("Playback interrupted by user")
        finally:
            self.producer.flush()
            logger.info("Playback concluded")


def main():
    settings = get_settings()
    streamer = HistoricalRaceStreamer(
        year=settings.default_playback_year,
        event=settings.default_playback_event,
        session=settings.default_playback_session,
        drivers=settings.playback_driver_list(),
        playback_speed=settings.default_playback_speed,
    )
    streamer.load_data()
    streamer.execute_playback()


if __name__ == "__main__":
    main()
