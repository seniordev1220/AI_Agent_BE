import os
import aiofiles
import uuid
from fastapi import UploadFile
from typing import List, Tuple
from datetime import datetime

class FileHandler:
    def __init__(self):
        self.upload_dir = "uploads"
        self.ensure_upload_directory()

    def ensure_upload_directory(self):
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)

    async def save_file(self, file: UploadFile, user_id: int) -> Tuple[str, str]:
        # Create user-specific directory
        user_dir = os.path.join(self.upload_dir, str(user_id))
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_extension = os.path.splitext(file.filename)[1]
        new_filename = f"{timestamp}_{unique_id}{file_extension}"
        
        # Save file
        file_path = os.path.join(user_dir, new_filename)
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)

        return file_path, new_filename

    def get_supported_extensions(self) -> List[str]:
        return ['.txt', '.pdf', '.doc', '.docx', '.csv', '.xlsx', '.json', '.md']

    def validate_file_extension(self, filename: str) -> bool:
        return any(filename.lower().endswith(ext) for ext in self.get_supported_extensions())

async def save_upload_file(file: UploadFile, destination: str) -> str:
    try:
        async with aiofiles.open(destination, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        return destination
    except Exception as e:
        if os.path.exists(destination):
            os.remove(destination)
        raise e 