from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader, UnstructuredExcelLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Any
import os

class DataSourceLoader:
    def __init__(self, source_type: str, connection_settings: Dict[str, Any]):
        self.source_type = source_type
        self.connection_settings = connection_settings
            
    async def load_and_split(self) -> List[Dict[str, Any]]:
        documents = await self._load_documents()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        splits = text_splitter.split_documents(documents)
        return [        
            {
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc in splits
        ]
            
    async def _load_documents(self):
        file_path = self.connection_settings["file_path"]
        if self.source_type == "file_upload":
            # Detect by extension
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".pdf":
                with open(file_path, "r", encoding="utf-8") as temp_file:
                    loader = PyPDFLoader(temp_file.name)
            elif ext == ".csv":
                loader = CSVLoader(file_path=file_path)
            elif ext in [".xls", ".xlsx"]:
                loader = UnstructuredExcelLoader(file_path=file_path)
            elif ext == ".txt":
                loader = TextLoader(file_path=file_path)
            else:
                raise ValueError(f"Unsupported uploaded file extension: {ext}")
        else:
            raise ValueError(f"Unsupported source_type: {self.source_type}")

        return loader.load()
