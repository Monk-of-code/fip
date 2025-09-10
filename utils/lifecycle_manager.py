"""
Lifecycle Manager for File Cleanup
Manages file lifecycle and cleanup based on upload success
"""

import os
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import LifecycleLog, UploadedImage, ResamplingLog
import logging

logger = logging.getLogger(__name__)

class LifecycleManager:
    """Manages file lifecycle and cleanup operations"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def _create_lifecycle_log(self, execution_id: str, filename: str, 
                            file_path: str, file_size_bytes: int) -> LifecycleLog:
        """Create a new lifecycle log entry"""
        lifecycle_log = LifecycleLog(
            execution_id=execution_id,
            filename=filename,
            file_path=file_path,
            file_type='tiff',
            file_size_bytes=file_size_bytes,
            created_time=datetime.utcnow(),
            download_status='pending',
            processing_status='pending',
            upload_status='pending',
            cleanup_status='pending',
            can_cleanup=False
        )
        self.db_session.add(lifecycle_log)
        return lifecycle_log
    
    def _update_lifecycle_log_status(self, execution_id: str, status_type: str, 
                                   status: str, can_cleanup: bool = False, 
                                   cleanup_reason: str = None) -> None:
        """Update lifecycle log status"""
        try:
            lifecycle_log = self.db_session.query(LifecycleLog).filter(
                LifecycleLog.execution_id == execution_id
            ).first()
            
            if lifecycle_log:
                if status_type == 'download':
                    lifecycle_log.download_status = status
                    lifecycle_log.download_time = datetime.utcnow()
                elif status_type == 'processing':
                    lifecycle_log.processing_status = status
                    lifecycle_log.processing_time = datetime.utcnow()
                elif status_type == 'upload':
                    lifecycle_log.upload_status = status
                    lifecycle_log.upload_time = datetime.utcnow()
                elif status_type == 'cleanup':
                    lifecycle_log.cleanup_status = status
                    lifecycle_log.cleanup_time = datetime.utcnow()
                
                lifecycle_log.can_cleanup = can_cleanup
                if cleanup_reason:
                    lifecycle_log.cleanup_reason = cleanup_reason
                
                self.db_session.commit()
                logger.info(f"Updated lifecycle log for {execution_id}: {status_type}={status}")
            else:
                logger.warning(f"No lifecycle log found for execution {execution_id}")
                
        except Exception as e:
            logger.error(f"Failed to update lifecycle log: {e}")
            self.db_session.rollback()
            raise
    
    # --------------------------
    # Resampling Log Management
    # --------------------------
    def create_resampling_log(self, execution_id: str, filename: str,
                              output_filename: str, input_res: float,
                              target_res: float, method: str = "bilinear",
                              compression: str = "lzw") -> ResamplingLog:
        """Create a new resampling log entry (pending state)"""
        resampling_log = ResamplingLog(
            execution_id=execution_id,
            filename=filename,
            output_filename=output_filename,
            input_resolution=input_res,
            target_resolution=target_res,
            resampling_method=method,
            compression=compression,
            status="pending",
            start_time=datetime.utcnow()
        )
        self.db_session.add(resampling_log)
        self.db_session.commit()
        logger.info(f"Created resampling log for {execution_id} - {filename}")
        return resampling_log





    def mark_upload_success(self, execution_id: str, geonode_resource_id: int, 
                          geonode_urls: dict) -> None:
        """Mark upload as successful and allow cleanup"""
        try:
            # Update lifecycle log
            self._update_lifecycle_log_status(
                execution_id, 'upload', 'success', 
                can_cleanup=True, 
                cleanup_reason='Successfully uploaded to GeoNode'
            )
            
            # Create uploaded image record
            lifecycle_log = self.db_session.query(LifecycleLog).filter(
                LifecycleLog.execution_id == execution_id
            ).first()
            
            if lifecycle_log:
                uploaded_image = UploadedImage(
                    filename=lifecycle_log.filename,
                    geonode_resource_id=geonode_resource_id,
                    geonode_resource_url=geonode_urls.get('resource_url', ''),
                    geonode_thumbnail_url=geonode_urls.get('thumbnail_url', ''),
                    geonode_detail_url=geonode_urls.get('detail_url', ''),
                    upload_time=datetime.utcnow(),
                    file_size_bytes=lifecycle_log.file_size_bytes,
                    status='uploaded',
                    execution_id=execution_id,
                    triggered_by='scheduled'  # or 'manual'
                )
                self.db_session.add(uploaded_image)
                self.db_session.commit()
                logger.info(f"Marked upload success for {execution_id}")
            else:
                logger.warning(f"No lifecycle log found for execution {execution_id}")
                
        except Exception as e:
            logger.error(f"Failed to mark upload success: {e}")
            self.db_session.rollback()
            raise
    
    def mark_upload_failure(self, execution_id: str, error_message: str) -> None:
        """Mark upload as failed and prevent cleanup"""
        try:
            self._update_lifecycle_log_status(
                execution_id, 'upload', 'failed', 
                can_cleanup=False, 
                cleanup_reason=f'Upload failed: {error_message}'
            )
            logger.info(f"Marked upload failure for {execution_id}")
        except Exception as e:
            logger.error(f"Failed to mark upload failure: {e}")
            self.db_session.rollback()
            raise
    
    def cleanup_successful_uploads(self) -> dict:
        """Clean up files that were successfully uploaded"""
        try:
            # Find files marked for cleanup
            cleanup_candidates = self.db_session.query(LifecycleLog).filter(
                LifecycleLog.can_cleanup == True,
                LifecycleLog.cleanup_status == 'pending'
            ).all()
            
            cleaned_files = []
            failed_cleanups = []
            
            for lifecycle_log in cleanup_candidates:
                try:
                    file_path = Path(lifecycle_log.file_path)
                    
                    # Delete local file if it exists
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Deleted local file: {file_path}")
                    
                    # Update cleanup status
                    self._update_lifecycle_log_status(
                        lifecycle_log.execution_id, 'cleanup', 'success'
                    )
                    
                    cleaned_files.append({
                        'filename': lifecycle_log.filename,
                        'file_path': lifecycle_log.file_path,
                        'execution_id': lifecycle_log.execution_id
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup {lifecycle_log.filename}: {e}")
                    self._update_lifecycle_log_status(
                        lifecycle_log.execution_id, 'cleanup', 'failed'
                    )
                    failed_cleanups.append({
                        'filename': lifecycle_log.filename,
                        'error': str(e)
                    })
            
            return {
                'status': 'completed',
                'cleaned_files': cleaned_files,
                'failed_cleanups': failed_cleanups,
                'total_cleaned': len(cleaned_files),
                'total_failed': len(failed_cleanups)
            }
            
        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def get_lifecycle_status(self) -> dict:
        """Get current lifecycle status"""
        try:
            total_logs = self.db_session.query(LifecycleLog).count()
            pending_cleanup = self.db_session.query(LifecycleLog).filter(
                LifecycleLog.can_cleanup == True,
                LifecycleLog.cleanup_status == 'pending'
            ).count()
            
            successful_uploads = self.db_session.query(UploadedImage).count()
            
            return {
                'total_lifecycle_logs': total_logs,
                'pending_cleanup': pending_cleanup,
                'successful_uploads': successful_uploads,
                'cleanup_ready': pending_cleanup > 0
            }
        except Exception as e:
            logger.error(f"Failed to get lifecycle status: {e}")
            return {'error': str(e)}