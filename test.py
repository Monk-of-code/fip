import requests
from pathlib import Path

# --- Configuration ---
GEONODE_URL = "http://fip.kenyaforestservice.org/api/v2/uploads/upload"
USERNAME = "admin"
PASSWORD = "70TMQKPctseMJQg"
auth = (USERNAME, PASSWORD)

# Local file paths
raster_file_path = "/data/fip/resampled/treecover2010_00N_030E_resampled.tif"
sld_file_path = "/data/fip/styles/treecover.sld"

# Metadata
title = "GLAD Forest Cover Test"
abstract = "Forest cover data from GLAD (Global Land Analysis & Discovery)"

# --- Prepare upload ---
files = {
    "base_file": open(raster_file_path, "rb"),
    "sld_file": open(sld_file_path, "rb"),
}

data = {
    "title": title,
    "abstract": abstract,
    "srid": "EPSG:4326"  # make sure CRS is set
}

# --- Upload request ---
try:
    response = requests.post(
        GEONODE_URL,
        auth=auth,
        files=files,
        data=data,
        timeout=900
    )

    print(GEONODE_URL)
    print("uploading...")

    if response.status_code in [200, 201]:
        print("✅ Upload successful!")
        print("Response:", response.json())
    else:
        print(f"❌ Upload failed: {response.status_code}")
        print(response.text)

except requests.exceptions.Timeout:
    print("❌ Upload timed out!")
except Exception as e:
    print(f"❌ Exception during upload: {e}")
