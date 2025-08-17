"""
Safe file cleanup utility for Windows temp files
Handles WinError 32: The process cannot access the file because it is being used by another process
"""
import os
import time
import tempfile
import logging

logger = logging.getLogger(__name__)

def safe_cleanup_temp_file(file_path, max_retries=3, delay=0.5):
    """
    Safely remove a temporary file, handling Windows file locking issues
    
    Args:
        file_path (str): Path to the file to remove
        max_retries (int): Maximum number of retry attempts
        delay (float): Delay between retries in seconds
    
    Returns:
        bool: True if file was successfully removed, False otherwise
    """
    if not os.path.exists(file_path):
        return True
    
    for attempt in range(max_retries):
        try:
            os.unlink(file_path)
            logger.info(f"✅ Successfully cleaned up temp file: {file_path}")
            return True
        except PermissionError as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Temp file cleanup retry {attempt + 1}/{max_retries}: {e}")
                time.sleep(delay)
            else:
                logger.error(f"❌ Failed to cleanup temp file after {max_retries} attempts: {file_path}")
                logger.error(f"Error: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during temp file cleanup: {e}")
            return False
    
    return False

def create_temp_zip_file(content_dict=None, suffix='.zip'):
    """
    Create a temporary ZIP file with optional content
    
    Args:
        content_dict (dict): Dictionary of filename -> content pairs
        suffix (str): File suffix for the temp file
    
    Returns:
        str: Path to the created temp file
    """
    import zipfile
    
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp_file.close()  # Close handle to avoid Windows locking issues
    
    if content_dict:
        with zipfile.ZipFile(temp_file.name, 'w') as zip_file:
            for filename, content in content_dict.items():
                if isinstance(content, str):
                    content = content.encode('utf-8')
                zip_file.writestr(filename, content)
    
    return temp_file.name

# Context manager for automatic cleanup
class TempZipFile:
    """Context manager for temporary ZIP files with automatic cleanup"""
    
    def __init__(self, content_dict=None, suffix='.zip'):
        self.content_dict = content_dict
        self.suffix = suffix
        self.file_path = None
    
    def __enter__(self):
        self.file_path = create_temp_zip_file(self.content_dict, self.suffix)
        return self.file_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_path:
            safe_cleanup_temp_file(self.file_path)

# Usage examples:
if __name__ == "__main__":
    # Example 1: Manual cleanup
    temp_path = create_temp_zip_file({
        'test1.txt': 'Hello World',
        'test2.txt': 'Test Content'
    })
    print(f"Created temp file: {temp_path}")
    safe_cleanup_temp_file(temp_path)
    
    # Example 2: Context manager (recommended)
    with TempZipFile({'image1.jpg': b'fake image data'}) as temp_zip:
        print(f"Using temp file: {temp_zip}")
        # File will be automatically cleaned up when exiting the context
