import os
import shutil
from datetime import datetime, timedelta
from typing import List
import asyncio

class FileCleanup:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir

    async def cleanup_old_files(self, days: int = 7):
        """Clean up files older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for user_dir in os.listdir(self.upload_dir):
            user_path = os.path.join(self.upload_dir, user_dir)
            if not os.path.isdir(user_path):
                continue

            for filename in os.listdir(user_path):
                file_path = os.path.join(user_path, filename)
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_modified < cutoff_date:
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"Error deleting {file_path}: {e}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)

    async def cleanup_processed_files(self, file_paths: List[str]):
        """Clean up files after they've been processed"""
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)

async def cleanup_old_files(directory: str, days: int):
    """Remove files older than specified days"""
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_modified < cutoff:
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}") 