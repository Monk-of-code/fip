"""
Raster Resampler with Compression
Resamples raster images, compresses them, and logs lifecycle in database
"""

import os
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import LifecycleLog
import logging
import rasterio
from rasterio.enums import Resampling

logger = logging.getLogger(__name__)

class RasterResampler:
    """Handles raster resampling, compression, and lifecycle logging"""

    def __init__(self, db_session: Session, output_dir: str = "/opt/airflow/fip/resampled"):
        self.db_session = db_session
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _log_resample(self, execution_id: str, input_path: Path, output_path: Path,
                      resampling_method: str, resolution: float) -> None:
        """Log resampling in database lifecycle log"""
        try:
            file_size = output_path.stat().st_size

            lifecycle_record = LifecycleLog(
                execution_id=execution_id,
                filename=output_path.name,
                file_path=str(output_path),
                file_type='tiff',
                file_size_bytes=file_size,
                processing_time=datetime.utcnow(),
                processing_status='success',
                local_path=str(output_path),
                can_cleanup=False,
                cleanup_status='pending',
                download_status='success'
            )

            self.db_session.add(lifecycle_record)
            self.db_session.commit()
            logger.info(f"Resample logged for {output_path.name}")

        except Exception as e:
            logger.error(f"Failed to log resample for {output_path.name}: {e}")
            self.db_session.rollback()
            raise

    def resample_raster(self, input_path: str, execution_id: str,
                        resampling_method: str = "bilinear", scale_factor: float = 0.5) -> dict:
        """
        Resample and compress a raster file using a simple scale factor.
        """
        try:
            input_path = Path(input_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Input raster not found: {input_path}")

            resampling_map = {
                "nearest": Resampling.nearest,
                "bilinear": Resampling.bilinear,
                "cubic": Resampling.cubic
            }

            if resampling_method not in resampling_map:
                raise ValueError(f"Invalid resampling method: {resampling_method}")

            output_filename = f"{input_path.stem}_resampled.tif"
            output_path = self.output_dir / output_filename

            with rasterio.open(input_path) as src:
                new_height = int(src.height * scale_factor)
                new_width = int(src.width * scale_factor)

                data = src.read(
                    out_shape=(src.count, new_height, new_width),
                    resampling=resampling_map[resampling_method]
                )

                profile = src.profile
                profile.update({
                    "driver": "GTiff",
                    "height": data.shape[1],
                    "width": data.shape[2],
                    "transform": src.transform * src.transform.scale(
                        (src.width / data.shape[2]),
                        (src.height / data.shape[1])
                    ),
                    "compress": "lzw"
                })

                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(data)

            self._log_resample(execution_id, input_path, output_path,
                               resampling_method, scale_factor)

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Resampled {input_path.name} -> {output_path.name} ({file_size_mb:.1f} MB)")

            return {
                "status": "success",
                "input_file": str(input_path),
                "output_file": str(output_path),
                "resampling_method": resampling_method,
                "scale_factor": scale_factor,
                "file_size_bytes": output_path.stat().st_size,
                "file_size_mb": file_size_mb
            }

        except Exception as e:
            logger.error(f"Resampling failed for {input_path}: {e}")
            return {
                "status": "failed",
                "input_file": str(input_path),
                "error": str(e)
            }
