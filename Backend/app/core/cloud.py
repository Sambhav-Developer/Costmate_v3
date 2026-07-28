import cloudinary
import cloudinary.uploader
from app.config import settings
from app.core.logging import logger

# Initialize Cloudinary Configuration
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

def upload_to_cloudinary(file_path: str, resource_type: str = "raw", project_name: str = "") -> str:
    """
    Uploads a local file to Cloudinary and returns the secure URL.
    resource_type="raw" allows non-image files like PDF and Excel.
    """
    folder_path = f"Costmate/{project_name}" if project_name else "Costmate"
    
    try:
        # Extract filename without extension to use as public_id
        import os
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        response = cloudinary.uploader.upload(
            file_path, 
            resource_type=resource_type,
            folder=folder_path,
            public_id=base_name,
            overwrite=True
        )
        url = response.get("secure_url")
        logger.info(f"Successfully uploaded {file_path} to Cloudinary: {url}")
        return url
    except Exception as e:
        logger.error(f"Failed to upload {file_path} to Cloudinary: {e}")
        return ""

def upload_to_cloudinary_bytes(file_data: bytes, filename: str, resource_type: str = "raw", project_name: str = "") -> str:
    """
    Uploads a byte string directly to Cloudinary without writing to disk.
    """
    folder_path = f"Costmate/{project_name}" if project_name else "Costmate"
    
    try:
        import os
        base_name = os.path.splitext(filename)[0]
        
        response = cloudinary.uploader.upload(
            file_data, 
            resource_type=resource_type,
            folder=folder_path,
            public_id=base_name,
            overwrite=True
        )
        url = response.get("secure_url")
        logger.info(f"Successfully uploaded {filename} to Cloudinary: {url}")
        return url
    except Exception as e:
        logger.error(f"Failed to upload {filename} to Cloudinary: {e}")
        return ""
