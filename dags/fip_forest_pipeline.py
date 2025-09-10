"""
FIP Forest Cover Pipeline DAG
Downloads GLAD forest cover images and uploads to GeoNode with SLD styling
Scheduled to run weekly on Mondays at 2 AM
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from pathlib import Path
import uuid
import logging

# Import our custom modules
import sys
import os
sys.path.append('/opt/airflow/fip')

from database import get_db_session, create_tables, test_connection
from utils import GLADDownloader, LifecycleManager
from resampling import RasterResampler
from upload import GeoNodeUploader

# Default arguments
default_args = {
    'owner': 'fip-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'catchup': False,
    'execution_timeout': timedelta(minutes=60),
}

# DAG definition
dag = DAG(
    'fip_forest_pipeline',
    default_args=default_args,
    description='FIP Forest Cover Pipeline - Download single GLAD image and upload to GeoNode',
    schedule='0 2 * * 1',  # Weekly on Monday at 2 AM
    max_active_runs=1,
    tags=['fip', 'forest-cover', 'glad', 'geonode'],
    doc_md="""
    ## FIP Forest Cover Pipeline - Single Image
    
    This pipeline downloads ONE GLAD forest cover image and uploads to GeoNode:
    1. Downloads treecover2010_00N_030E.tif from GLAD
    2. Tracks download in PostgreSQL with deduplication
    3. Uploads image to GeoNode with metadata
    4. Applies SLD styling from styles/TREECOVER.sld
    5. Cleans up file only after successful upload
    6. Logs complete lifecycle in database
    
    **Schedule**: Weekly on Mondays at 2 AM
    **Target Image**: treecover2010_00N_030E.tif (SINGLE IMAGE ONLY)
    **Styling**: TREECOVER.sld from styles folder
    """,
)

def check_services(**context):
    """Check that all required services are available"""
    logger = logging.getLogger(__name__)
    
    try:
        # Test database connection
        if not test_connection():
            raise Exception("Database connection failed")
        
        # Check if styles directory exists
        styles_dir = Path('/opt/airflow/styles')
        if not styles_dir.exists():
            raise Exception(f"Styles directory not found: {styles_dir}")
        
        sld_file = styles_dir / 'TREECOVER.sld'
        if not sld_file.exists():
            raise Exception(f"SLD file not found: {sld_file}")
        
        logger.info("All services are available")
        return True
        
    except Exception as e:
        logger.error(f"Service check failed: {e}")
        raise

def initialize_execution(**context):
    """Initialize execution and create database tables"""
    logger = logging.getLogger(__name__)
    
    try:
        # Create database tables
        create_tables()
        
        # Generate execution ID
        execution_id = str(uuid.uuid4())
        context['task_instance'].xcom_push(key='execution_id', value=execution_id)
        
        logger.info(f"Execution initialized with ID: {execution_id}")
        return execution_id
        
    except Exception as e:
        logger.error(f"Execution initialization failed: {e}")
        raise

def download_glad_image(**context):
    """Download GLAD forest cover image (treecover2010_00N_030E.tif)"""
    logger = logging.getLogger(__name__)
    
    try:
        execution_id = context['task_instance'].xcom_pull(key='execution_id')
        db_session = get_db_session()
        
        # Initialize downloader
        downloader = GLADDownloader(db_session)
        
        # Download the single image
        result = downloader.download_glad_image(execution_id)
        
        if result['status'] == 'success':
            logger.info(f"Successfully downloaded: {result['filename']}")
            context['task_instance'].xcom_push(key='download_result', value=result)
            return result
        elif result['status'] == 'skipped':
            logger.info(f"Image already exists: {result['filename']}")
            context['task_instance'].xcom_push(key='download_result', value=result)
            return result
        else:
            raise Exception(f"Download failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Download task failed: {e}")
        raise
    finally:
        if 'db_session' in locals():
            db_session.close()

def resample_raster_task(**context):
    """Resample raster with compression and log lifecycle"""
    logger = logging.getLogger(__name__)
    
    try:
        execution_id = context['task_instance'].xcom_pull(key='execution_id')
        download_result = context['task_instance'].xcom_pull(key='download_result')
        
        if not download_result or download_result.get('status') not in ('success','skipped'):
            raise Exception("No valid raster to resample from download_result XCom")
        
        input_raster = download_result['file_path']  # match your downloader's return format
        db_session = get_db_session()
        
        # Initialize resampler
        resampler = RasterResampler(db_session, output_dir="/opt/airflow/fip/resampled")
        
        # Perform resampling
        result = resampler.resample_raster(
            input_path=input_raster,
            execution_id=execution_id,
            resampling_method="bilinear"                 # e.g. 30m target resolution
        )
        
        if result['status'] == 'success':
            logger.info(f"Successfully resampled: {result['output_file']}")
            context['task_instance'].xcom_push(key='resample_result', value=result)
            return result
        else:
            raise Exception(f"Resample failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Resample task failed: {e}")
        raise
    finally:
        if 'db_session' in locals():
            db_session.close()

def upload_to_geonode(**context):
    """Upload image to GeoNode with SLD styling"""
    logger = logging.getLogger(__name__)
    
    try:
        execution_id = context['task_instance'].xcom_pull(key='execution_id')
        resample_result = context['task_instance'].xcom_pull(key='resample_result')
        db_session = get_db_session()
        
        # Initialize uploader
        uploader = GeoNodeUploader(db_session)
        
        # Upload with styling
        file_path = Path(resample_result['output_file'])
        upload_result = uploader.upload_with_styling(file_path, execution_id)
        
        if upload_result['status'] == 'success':
            logger.info(f"Successfully uploaded to GeoNode: {upload_result['resource_id']}")
            
            # Mark upload success for cleanup
            lifecycle_manager = LifecycleManager(db_session)
            geonode_urls = {
                'resource_url': upload_result.get('resource_url', ''),
                'thumbnail_url': upload_result.get('thumbnail_url', ''),
                'detail_url': upload_result.get('detail_url', '')
            }
            lifecycle_manager.mark_upload_success(
                execution_id, 
                upload_result['resource_id'], 
                geonode_urls
            )
            
            context['task_instance'].xcom_push(key='upload_result', value=upload_result)
            return upload_result
        else:
            # Mark upload failure
            lifecycle_manager = LifecycleManager(db_session)
            lifecycle_manager.mark_upload_failure(execution_id, upload_result.get('error', 'Unknown error'))
            raise Exception(f"Upload failed: {upload_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Upload task failed: {e}")
        raise
    finally:
        if 'db_session' in locals():
            db_session.close()

def cleanup_files(**context):
    """Clean up files that were successfully uploaded"""
    logger = logging.getLogger(__name__)
    
    try:
        db_session = get_db_session()
        lifecycle_manager = LifecycleManager(db_session)
        
        # Clean up successfully uploaded files
        cleanup_result = lifecycle_manager.cleanup_successful_uploads()
        
        if cleanup_result['status'] == 'completed':
            logger.info(f"Cleanup completed: {cleanup_result['total_cleaned']} files cleaned")
            return cleanup_result
        else:
            logger.warning(f"Cleanup had issues: {cleanup_result}")
            return cleanup_result
            
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        raise
    finally:
        if 'db_session' in locals():
            db_session.close()

def finalize_execution(**context):
    """Finalize execution and log summary"""
    logger = logging.getLogger(__name__)
    
    try:
        execution_id = context['task_instance'].xcom_pull(key='execution_id')
        download_result = context['task_instance'].xcom_pull(key='download_result')
        upload_result = context['task_instance'].xcom_pull(key='upload_result')
        
        logger.info("=" * 60)
        logger.info("FIP FOREST PIPELINE EXECUTION COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Execution ID: {execution_id}")
        logger.info(f"Download Status: {download_result['status']}")
        logger.info(f"Upload Status: {upload_result['status']}")
        logger.info(f"Resource ID: {upload_result.get('resource_id', 'N/A')}")
        logger.info(f"Styling Applied: {upload_result.get('styling', {}).get('status', 'N/A')}")
        logger.info("=" * 60)
        
        return {
            'execution_id': execution_id,
            'download_result': download_result,
            'upload_result': upload_result,
            'status': 'completed'
        }
        
    except Exception as e:
        logger.error(f"Finalization failed: {e}")
        raise

# Task definitions
check_services_task = PythonOperator(
    task_id='check_services',
    python_callable=check_services,
    dag=dag,
)

initialize_execution_task = PythonOperator(
    task_id='initialize_execution',
    python_callable=initialize_execution,
    dag=dag,
)

download_glad_image_task = PythonOperator(
    task_id='download_glad_image',
    python_callable=download_glad_image,
    dag=dag,
)


resample_raster = PythonOperator(
    task_id="resample_raster",
    python_callable=resample_raster_task,
    provide_context=True,
    dag=dag,
)

upload_to_geonode_task = PythonOperator(
    task_id='upload_to_geonode',
    python_callable=upload_to_geonode,
    dag=dag,
)

cleanup_files_task = PythonOperator(
    task_id='cleanup_files',
    python_callable=cleanup_files,
    dag=dag,
)

finalize_execution_task = PythonOperator(
    task_id='finalize_execution',
    python_callable=finalize_execution,
    dag=dag,
)

# Task dependencies
check_services_task >> initialize_execution_task >> download_glad_image_task >> resample_raster >>upload_to_geonode_task >> cleanup_files_task >> finalize_execution_task