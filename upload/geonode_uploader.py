"""
GeoNode Uploader with SLD Styling
Uploads raster images to GeoNode together with SLD styles
"""

import os
import requests
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import MetadataLog
import logging

logger = logging.getLogger(__name__)

class GeoNodeUploader:
    """Uploads raster images together with SLD styling to GeoNode."""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.geonode_url = os.getenv(
            'GEONODE_URL', "http://fip.kenyaforestservice.org/api/v2/uploads/upload"
        )
        self.username = os.getenv('LOGIN_NAME', 'admin')
        self.password = os.getenv('LOGIN_PASSWORD', 'admin')
        self.styles_dir = Path(os.getenv('STYLES_DIR', '/opt/airflow/fip/styles'))
        self.styles_dir.mkdir(parents=True, exist_ok=True)  # Ensure it exists

    
    def upload_raster_with_sld(
        self, raster_file: Path, sld_file_name: str, title: str, abstract: str, execution_id: str
    ):
        """Upload raster + SLD to GeoNode and log metadata (streamed)."""
        try:
            if not raster_file.exists():
                raise FileNotFoundError(f"Raster file not found: {raster_file}")

            sld_file_path = self.styles_dir / sld_file_name
            if not sld_file_path.exists():
                raise FileNotFoundError(f"SLD file not found: {sld_file_path}")

            # Metadata form
            data = {
                'title': title,
                'abstract': abstract,
                'srid': 'EPSG:4326'
            }

            logger.info(f"Uploading raster {raster_file.name} with SLD {sld_file_name}...")

            # Stream upload using 'with' to auto-close files
            with open(raster_file, 'rb') as raster, open(sld_file_path, 'rb') as sld:
                files = {'base_file': raster, 'sld_file': sld}
                response = requests.post(
                    self.geonode_url,
                    auth=(self.username, self.password),
                    files=files,
                    data=data,
                    timeout=(600, 7200)
                )
                response.raise_for_status()
                result = response.json()

            # Log metadata
            metadata_log = MetadataLog(
                uploaded_image_id=result.get('id'),
                style_name=sld_file_name,
                sld_file_path=str(sld_file_path),
                geonode_style_url=result.get('style_url', ''),
                applied_time=datetime.utcnow(),
                status='applied',
                execution_id=execution_id
            )
            self.db_session.add(metadata_log)
            self.db_session.commit()

            logger.info(f"Upload successful: {raster_file.name}, resource ID: {result.get('id')}")

            return {
                'status': 'success',
                'resource_id': result.get('id'),
                'resource_url': result.get('resource_url', ''),
                'thumbnail_url': result.get('thumbnail_url', ''),
                'detail_url': result.get('detail_url', ''),
                'response_code': response.status_code
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"GeoNode upload failed: {e}")
            return {'status': 'failed', 'error': str(e), 'response_code': getattr(e.response, 'status_code', None)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {'status': 'failed', 'error': str(e)}