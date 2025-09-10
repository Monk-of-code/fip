"""
GeoNode Uploader with Lifecycle Integration
Uploads raster + SLD to GeoNode, tracks upload in lifecycle + uploaded_images
"""

import logging
import requests
from pathlib import Path
from sqlalchemy.orm import Session
from database.models import UploadedImage
from utils.lifecycle_manager import LifecycleManager

logger = logging.getLogger(__name__)


class GeoNodeUploader:
    """Handles GeoNode raster uploads with SLD and lifecycle logging"""

    def __init__(self, db_session: Session,
                 geonode_url: str,
                 username: str,
                 password: str):
        self.db_session = db_session
        self.geonode_url = geonode_url.rstrip("/")
        self.auth = (username, password)
        self.lifecycle = LifecycleManager(db_session)

    def upload_raster(self, execution_id: str, raster_path: str, sld_path: str,
                      title: str, abstract: str, srid: str = "EPSG:4326") -> dict:
        """
        Upload raster with SLD to GeoNode and update lifecycle logs.
        """
        raster_path = Path(raster_path)
        sld_path = Path(sld_path)

        try:
            if not raster_path.exists():
                raise FileNotFoundError(f"Raster not found: {raster_path}")
            if not sld_path.exists():
                raise FileNotFoundError(f"SLD not found: {sld_path}")

            files = {
                "base_file": open(raster_path, "rb"),
                "sld_file": open(sld_path, "rb"),
            }

            data = {
                "title": title,
                "abstract": abstract,
                "srid": srid,
            }

            url = f"{self.geonode_url}/api/v2/uploads/upload"
            logger.info(f"Uploading {raster_path.name} to GeoNode: {url}")

            response = requests.post(url, auth=self.auth, files=files, data=data)

            # Handle response
            if response.status_code != 200:
                self.lifecycle.mark_upload_failure(execution_id, response.text)
                return {
                    "status": "failed",
                    "error": response.text,
                    "http_code": response.status_code
                }

            result = response.json()
            upload_id = result.get("id")
            detail_url = result.get("detail_url", "")
            thumb_url = result.get("thumbnail_url", "")
            resource_url = result.get("resource_url", "")

            # Mark lifecycle success
            self.lifecycle.mark_upload_success(
                execution_id,
                geonode_resource_id=upload_id,
                geonode_urls={
                    "resource_url": resource_url,
                    "thumbnail_url": thumb_url,
                    "detail_url": detail_url
                }
            )

            return {
                "status": "success",
                "upload_id": upload_id,
                "urls": {
                    "resource_url": resource_url,
                    "thumbnail_url": thumb_url,
                    "detail_url": detail_url
                }
            }

        except Exception as e:
            logger.error(f"Upload failed for {raster_path}: {e}")
            self.lifecycle.mark_upload_failure(execution_id, str(e))
            return {
                "status": "failed",
                "error": str(e),
                "file": str(raster_path)
            }

    def get_upload_status(self, upload_id: int) -> dict:
        """
        Query GeoNode for upload status.
        """
        try:
            url = f"{self.geonode_url}/api/v2/uploads/{upload_id}/"
            logger.info(f"Checking status for upload ID {upload_id}")

            response = requests.get(url, auth=self.auth)

            if response.status_code != 200:
                return {
                    "status": "failed",
                    "error": response.text,
                    "http_code": response.status_code
                }

            return {
                "status": "success",
                "upload_id": upload_id,
                "upload_status": response.json()
            }

        except Exception as e:
            logger.error(f"Status check failed for upload {upload_id}: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "upload_id": upload_id
            }
