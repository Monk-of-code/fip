"""
Database Models for FIP Project
Tracks image downloads, uploads, and lifecycle management
"""


from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime


from sqlalchemy.sql.operators import as_

Base = declarative_base()

class ImageDeduplication(Base):
    """Tracks downloaded images to prevent re-downloads"""
    __tablename__ = 'image_deduplication'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), unique=True, nullable=False)
    extent = Column(String(50), nullable=False)  # e.g., "00N_030E"
    original_url = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256 hash
    first_downloaded = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, default=datetime.utcnow)
    download_count = Column(Integer, default=1)
    status = Column(String(20), default='downloaded')  # downloaded, processing, uploaded, failed

class LifecycleLog(Base):
    """Tracks complete file lifecycle from download to cleanup"""
    __tablename__ = 'lifecycle_log'
    
    id = Column(Integer, primary_key=True)
    execution_id = Column(String(36), nullable=False)  # UUID for this execution
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(20), default='tiff')
    file_size_bytes = Column(Integer, nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow)
    download_time = Column(DateTime)
    processing_time = Column(DateTime)
    upload_time = Column(DateTime)
    cleanup_time = Column(DateTime)
    download_status = Column(String(20), default='pending')  # pending, success, failed
    processing_status = Column(String(20), default='pending')
    upload_status = Column(String(20), default='pending')
    cleanup_status = Column(String(20), default='pending')
    storage_type = Column(String(20), default='local')  # local, minio
    minio_bucket = Column(String(100))
    minio_object_key = Column(String(255))
    local_path = Column(Text)
    can_cleanup = Column(Boolean, default=False)
    cleanup_reason = Column(Text)

class ResamplingLog(Base):
   #Tracks raster resampling and compression before upload
    __tablename__ = 'resampling_log'
    
    id = Column(Integer, primary_key=True)
    execution_id = Column(String(36), nullable=False)  # UUID for this execution
    filename = Column(String(255), nullable=False)     # input file
    output_filename = Column(String(255), nullable=False)  # processed file
    input_resolution = Column(Float, nullable=False)   # original pixel size (m)
    target_resolution = Column(Float, nullable=False)  # resampled resolution (m)
    resampling_method = Column(String(20), default='bilinear')  # nearest, bilinear, bicubic
    compression = Column(String(20), default='lzw')    # compression type
    status = Column(String(20), default='pending')     # pending, success, failed
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    processing_time_sec = Column(Float)
    error_message = Column(Text)
    processed_file_size_bytes = Column(Integer)
    triggered_by = Column(String(20), default='pipeline')  # pipeline, manual   

class UploadedImage(Base):
    """Tracks images uploaded to GeoNode"""
    __tablename__ = 'uploaded_images'
    
    id = Column(Integer,primary_key=True)
    filename = Column(String(255), nullable=False)
    geonode_resource_id = Column(UUID(as_uuid=True),nullable=False)
    geonode_resource_url = Column(Text, nullable=False)
    geonode_thumbnail_url = Column(Text)
    geonode_detail_url = Column(Text)
    upload_time = Column(DateTime, default=datetime.utcnow)
    file_size_bytes = Column(Integer, nullable=False)
    status = Column(String(20), default='uploaded')  # uploaded, styled, failed
    server_response_code = Column(Integer)
    server_response_message = Column(Text)
    execution_id = Column(String(36), nullable=False)
    triggered_by = Column(String(20), default='scheduled')  # scheduled, manual

class MetadataLog(Base):
    """Tracks metadata extraction and SLD styling"""
    __tablename__ = 'metadata_log'
    
    id = Column(Integer, primary_key=True)
    uploaded_image_id = Column(Integer, ForeignKey('uploaded_images.id'),nullable=False)
    style_name = Column(String(100), nullable=False)
    sld_file_path = Column(Text, nullable=False)
    geonode_style_url = Column(Text)
    applied_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='applied')  # applied, failed
    execution_id = Column(String(36), nullable=False)
    
    # Relationship
    uploaded_image = relationship("UploadedImage", back_populates="metadata_logs")

# Add relationship to UploadedImage
UploadedImage.metadata_logs = relationship("MetadataLog", back_populates="uploaded_image")