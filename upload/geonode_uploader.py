"""
GeoNode Uploader (Airflow-compatible, CSRF-safe)
Uploads raster + SLD to GeoNode using basic auth, logs outcome to lifecycle manager.
"""

import logging
from pathlib import Path
import requests
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from utils.lifecycle_manager import LifecycleManager

logger = logging.getLogger(__name__)

class GeoNodeUploader:
    """Uploader with lifecycle + DB logging, Airflow-compatible."""

    def __init__(self, db_session: Session, geonode_url: str, username: str, password: str, default_sld: str):
        self.db_session = db_session
        self.url = geonode_url
        self.auth = (username, password)
        self.default_sld = Path(default_sld)
        self.lifecycle = LifecycleManager(db_session)

    def upload_raster(self, execution_id: str, raster_path: str) -> dict:
        """
        Upload raster to GeoNode using basic auth, log result.
        Only raster_path is required.
        """
        raster_path = Path(raster_path)

        if not raster_path.exists():
            raise FileNotFoundError(f"Raster not found: {raster_path}")
        if not self.default_sld.exists():
            raise FileNotFoundError(f"SLD not found: {self.default_sld}")

        # Metadata
        title = f"Upload: {raster_path.stem}"
        abstract = "Forest cover data from GLAD (Global Land Analysis & Discovery)"

        files = {
            "base_file": open(raster_path, "rb"),
            "sld_file": open(self.default_sld, "rb"),
        }

        data = {
            "title": title,
            "abstract": abstract,
            "srid": "EPSG:4326"
        }

        logger.info(f"Uploading {raster_path.name} to GeoNode at {self.url}")

        try:
            response = requests.post(
                self.url,
                auth=self.auth,
                files=files,
                data=data,
                timeout=900
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info("✅ Upload successful")
                
                
                
                resource = result.get("resource", {})

                geonode_resource_uuid = resource.get("id") or uuid.UUID(execution_id)
                geonode_resource_id= geonode_resource_uuid.int % (2**31)
                geonode_urls = {
                    "resource_url": resource.get("url", ""),
                    "thumbnail_url": resource.get("thumbnail_url", ""),
                    "detail_url": resource.get("detail_url", "")
                }

                print (result)
                # Log success in lifecycle
                self.lifecycle.mark_upload_success(
                    execution_id,
                    geonode_resource_id=geonode_resource_id,
                    geonode_urls=geonode_urls
                )
                return {"status": "success", "response": result}

            else:
                logger.error(f"❌ Upload failed: {response.status_code} {response.text}")
                self.lifecycle.mark_upload_failure(execution_id, response.text)
                return {"status": "failed", "error": response.text}

        except requests.exceptions.Timeout:
            logger.error("❌ Upload timed out")
            self.lifecycle.mark_upload_failure(execution_id, "timeout")
            return {"status": "failed", "error": "timeout"}

        except Exception as e:
            logger.error(f"❌ Exception during upload: {e}")
            self.lifecycle.mark_upload_failure(execution_id, str(e))
            return {"status": "failed", "error": str(e)}
