"""
GLAD Image Downloader with Deduplication
Downloads GLAD forest cover images and tracks them in database
"""

import os
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import ImageDeduplication, LifecycleLog
import logging

logger = logging.getLogger(__name__)

class GLADDownloader:
    """Handles GLAD image downloads with deduplication"""
    
    def __init__(self, db_session: Session, output_dir: str = "/opt/airflow/fip/downloads"):
        self.db_session = db_session
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # GLAD base URL for tree cover 2010 - SINGLE IMAGE ONLY
        self.base_url = "https://glad.umd.edu/Potapov/TCC_2010/"
        self.target_image = "treecover2010_00N_030E.tif"
        
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _is_already_downloaded(self, filename: str) -> bool:
        """Check if image is already downloaded and tracked"""
        existing = self.db_session.query(ImageDeduplication).filter(
            ImageDeduplication.filename == filename
        ).first()
        return existing is not None
    
    def _log_download(self, filename: str, extent: str, original_url: str, 
                     file_path: Path, execution_id: str) -> None:
        """Log download in database"""
        try:
            file_hash = self._get_file_hash(file_path)
            file_size = file_path.stat().st_size
            
            # Check if already exists
            existing = self.db_session.query(ImageDeduplication).filter(
                ImageDeduplication.filename == filename
            ).first()
            
            if existing:
                # Update existing record
                existing.last_checked = datetime.utcnow()
                existing.download_count += 1
                existing.status = 'downloaded'
            else:
                # Create new record
                dedup_record = ImageDeduplication(
                    filename=filename,
                    extent=extent,
                    original_url=original_url,
                    file_hash=file_hash,
                    first_downloaded=datetime.utcnow(),
                    last_checked=datetime.utcnow(),
                    download_count=1,
                    status='downloaded'
                )
                self.db_session.add(dedup_record)
            
            # Create lifecycle log
            lifecycle_record = LifecycleLog(
                execution_id=execution_id,
                filename=filename,
                file_path=str(file_path),
                file_type='tiff',
                file_size_bytes=file_size,
                download_time=datetime.utcnow(),
                download_status='success',
                local_path=str(file_path),
                can_cleanup=False  # Don't cleanup until uploaded
            )
            self.db_session.add(lifecycle_record)
            
            self.db_session.commit()
            logger.info(f"Download logged for {filename}")
            
        except Exception as e:
            logger.error(f"Failed to log download for {filename}: {e}")
            self.db_session.rollback()
            raise
    
    def download_glad_image(self, execution_id: str) -> dict:
        """
        Download the single GLAD tree cover image (treecover2010_00N_030E.tif)
        
        Args:
            execution_id: UUID for this execution
            
        Returns:
            dict: Download result with file path and metadata
        """
        try:
            filename = self.target_image  # treecover2010_00N_030E.tif
            file_path = self.output_dir / filename
            original_url = f"{self.base_url}{filename}"
            
            # Check if already downloaded
            if self._is_already_downloaded(filename):
                logger.info(f"Image {filename} already exists, skipping download")
                return {
                    'status': 'skipped',
                    'filename': filename,
                    'file_path': str(file_path),
                    'reason': 'already_downloaded'
                }
            
            # Download the file
            logger.info(f"Downloading {filename} from {original_url}")
            response = requests.get(original_url, stream=True)
            response.raise_for_status()
            
            # Save file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify download
            if not file_path.exists() or file_path.stat().st_size == 0:
                raise Exception("Downloaded file is empty or doesn't exist")
            
            # Log download
            self._log_download(filename, "00N_030E", original_url, file_path, execution_id)
            
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            logger.info(f"Successfully downloaded {filename} ({file_size_mb:.1f} MB)")
            
            return {
                'status': 'success',
                'filename': filename,
                'file_path': str(file_path),
                'file_size_bytes': file_path.stat().st_size,
                'file_size_mb': file_size_mb,
                'extent': "00N_030E",
                'original_url': original_url
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Download failed for {self.target_image}: {e}")
            return {
                'status': 'failed',
                'filename': filename,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error downloading {self.target_image}: {e}")
            return {
                'status': 'failed',
                'filename': filename,
                'error': str(e)
            }
    
    def get_download_status(self) -> dict:
        """Get status of all downloaded images"""
        try:
            records = self.db_session.query(ImageDeduplication).all()
            return {
                'total_downloaded': len(records),
                'images': [
                    {
                        'filename': r.filename,
                        'extent': r.extent,
                        'status': r.status,
                        'first_downloaded': r.first_downloaded.isoformat(),
                        'download_count': r.download_count
                    }
                    for r in records
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get download status: {e}")
            return {'error': str(e)}