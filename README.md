# FIP Forest Cover Pipeline - Single Image

A containerized Airflow pipeline that downloads ONE GLAD forest cover image and uploads it to GeoNode with SLD styling.

##  **Project Overview**

This project implements a complete workflow for:
- **Downloading** ONE GLAD forest cover image (treecover2010_00N_030E.tif)
- **Deduplication** to prevent re-downloading existing images
- **Uploading** to GeoNode with metadata
- **Applying SLD styling** from `styles/TREECOVER.sld`
- **Database logging** of complete lifecycle
- **Cleanup** of file only after successful upload
- **Weekly scheduling** via Airflow

##  **Project Structure**

```
fip/
├── database/           # Database models and connection
│   ├── __init__.py
│   ├── models.py      # SQLAlchemy models
│   └── database.py    # Connection utilities
├── dags/              # Airflow DAGs
│   └── fip_forest_pipeline.py
├── upload/            # GeoNode upload functionality
│   ├── __init__.py
│   └── geonode_uploader.py
├── utils/             # Utility modules
│   ├── __init__.py
│   ├── glad_downloader.py
│   └── lifecycle_manager.py
├── tests/             # Test suite
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_glad_downloader.py
│   ├── test_geonode_uploader.py
│   ├── test_lifecycle_manager.py
│   └── run_all_tests.py
├── styles/            # SLD styling files
│   └── TREECOVER.sld
├── docker-compose.yml # Docker services
├── dockerfile         # Airflow container
├── requirements.txt   # Python dependencies
├── .env              # Environment variables
└── sample.env        # Sample environment
```

## 🚀 **Quick Start**

### **1. Environment Setup**
```bash
# Copy sample environment
cp sample.env .env

# Edit .env with your GeoNode credentials
nano .env
```

### **2. Start Services**
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### **3. Initialize Database**
```bash
# Create database tables
docker-compose exec airflow-webserver python -c "from database import create_tables; create_tables()"
```

### **4. Access Airflow UI**
- URL: http://localhost:8085
- Username: `airflow`
- Password: `airflow`

### **5. Run Pipeline**
1. Go to Airflow UI
2. Find `fip_forest_pipeline` DAG
3. Toggle it ON
4. Click "Trigger DAG" to run manually

## 🔧 **Configuration**

### **Environment Variables (.env)**

```bash
# GeoNode Configuration (REQUIRED)
GEONODE_URL=http://your-geonode.com/api/v2/uploads/upload/
LOGIN_NAME=your_username
LOGIN_PASSWORD=your_password

# Database Configuration
DATABASE_URL=postgresql://airflow:airflow@postgres:5432/airflow

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=fip-forest-data

# Processing Configuration
PROCESSING_APPROACH=individual
MAX_MEMORY_GB=2
```

## 📊 **Database Schema**

### **ImageDeduplication**
- Tracks downloaded images to prevent re-downloads
- Fields: filename, extent, original_url, file_hash, status

### **LifecycleLog**
- Tracks complete file lifecycle
- Fields: execution_id, filename, file_path, download_time, upload_time, cleanup_time, status

### **UploadedImage**
- Tracks GeoNode uploads
- Fields: filename, geonode_resource_id, geonode_resource_url, upload_time, status

### **MetadataLog**
- Tracks SLD styling applications
- Fields: uploaded_image_id, style_name, sld_file_path, applied_time, status

## 🧪 **Testing**

### **Run All Tests**
```bash
# Run comprehensive test suite
docker-compose exec airflow-webserver python tests/run_all_tests.py
```

### **Run Individual Tests**
```bash
# Test database
docker-compose exec airflow-webserver python tests/test_database.py

# Test GLAD downloader
docker-compose exec airflow-webserver python tests/test_glad_downloader.py

# Test GeoNode uploader
docker-compose exec airflow-webserver python tests/test_geonode_uploader.py

# Test lifecycle manager
docker-compose exec airflow-webserver python tests/test_lifecycle_manager.py
```

## 📋 **Pipeline Workflow**

1. **Check Services** - Verify all components are ready
2. **Initialize Execution** - Create database tables and generate execution ID
3. **Download GLAD Image** - Download treecover2010_00N_030E.tif with deduplication
4. **Upload to GeoNode** - Upload with metadata and apply SLD styling
5. **Cleanup Files** - Delete files only after successful upload
6. **Finalize Execution** - Log summary and completion status

## 🎨 **SLD Styling**

The pipeline automatically applies styling from `styles/TREECOVER.sld`:
- **Color Map**: Green gradient for forest cover values (0-100)
- **Transparency**: Semi-transparent overlay
- **Classification**: Continuous color ramp

## 📈 **Monitoring**

### **Airflow UI**
- Monitor DAG execution
- View task logs
- Check execution history

### **Database Queries**
```sql
-- Check download status
SELECT * FROM image_deduplication;

-- Check upload status
SELECT * FROM uploaded_images;

-- Check lifecycle logs
SELECT * FROM lifecycle_log;

-- Check styling applications
SELECT * FROM metadata_log;
```

## 🔍 **Troubleshooting**

### **Common Issues**

1. **Database Connection Failed**
   ```bash
   # Check PostgreSQL service
   docker-compose logs postgres
   ```

2. **GeoNode Upload Failed**
   ```bash
   # Check GeoNode credentials in .env
   # Verify GeoNode URL is accessible
   ```

3. **SLD Styling Failed**
   ```bash
   # Check if styles/TREECOVER.sld exists
   # Verify SLD file content is valid XML
   ```

### **Logs**
```bash
# View Airflow logs
docker-compose logs airflow-webserver
docker-compose logs airflow-scheduler
docker-compose logs airflow-worker

# View specific task logs in Airflow UI
```

## 🚀 **Deployment**

### **Production Considerations**

1. **Environment Variables**
   - Use secure passwords
   - Set proper GeoNode URLs
   - Configure database credentials

2. **Database**
   - Use external PostgreSQL for production
   - Set up database backups
   - Monitor database performance

3. **Storage**
   - Configure MinIO for production
   - Set up lifecycle policies
   - Monitor storage usage

4. **Security**
   - Use HTTPS for GeoNode
   - Secure database connections
   - Regular security updates

## 📝 **API Reference**

### **GLADDownloader**
```python
downloader = GLADDownloader(db_session, output_dir)
result = downloader.download_glad_tile('00N_030E', execution_id)
```

### **GeoNodeUploader**
```python
uploader = GeoNodeUploader(db_session)
result = uploader.upload_with_styling(file_path, execution_id, metadata)
```

### **LifecycleManager**
```python
manager = LifecycleManager(db_session)
manager.mark_upload_success(execution_id, resource_id, geonode_urls)
cleanup_result = manager.cleanup_successful_uploads()
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 **License**

This project is licensed under the MIT License.

## 🆘 **Support**

For support and questions:
- Check the troubleshooting section
- Review the test suite
- Check Airflow logs
- Verify environment configuration