import io
import re
from typing import Optional
import pymupdf
import docx
from fastapi import HTTPException, status
from backend.app.models.resume import CandidateProfile


class ResumeService:
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/octet-stream"  # sometimes sent by CLI/curl
    }

    def __init__(self):
        # In-memory storage for the active candidate profile until database integration (Part C)
        self._current_profile: Optional[CandidateProfile] = None

    def validate_file_extension(self, filename: str, content_type: Optional[str] = None):
        """Ensure file is either a PDF or DOCX file."""
        if not filename or "." not in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file: filename missing or has no extension."
            )
        
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Only PDF (.pdf) and DOCX (.docx) files are supported."
            )
        return ext

    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF pages using PyMuPDF."""
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            extracted_pages = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text:
                    extracted_pages.append(text)
            doc.close()
            full_text = "\n".join(extracted_pages).strip()
            return self._clean_text(full_text)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to read and parse PDF file: {str(e)}"
            )

    def extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX paragraphs and tables using python-docx."""
        try:
            stream = io.BytesIO(file_bytes)
            doc = docx.Document(stream)
            extracted_paragraphs = []
            
            # Paragraphs
            for p in doc.paragraphs:
                clean_p = p.text.strip()
                if clean_p:
                    extracted_paragraphs.append(clean_p)
            
            # Tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        extracted_paragraphs.append(" | ".join(row_text))

            full_text = "\n".join(extracted_paragraphs).strip()
            return self._clean_text(full_text)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to read and parse DOCX file: {str(e)}"
            )

    def extract_text(self, file_bytes: bytes, extension: str) -> str:
        """Dispatch text extraction based on file extension."""
        if extension == ".pdf":
            return self.extract_text_from_pdf(file_bytes)
        elif extension == ".docx":
            return self.extract_text_from_docx(file_bytes)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported extension {extension}"
            )

    def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Store the current profile."""
        self._current_profile = profile
        return profile

    def get_current_profile(self) -> Optional[CandidateProfile]:
        """Retrieve the active candidate profile."""
        return self._current_profile

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize line breaks and remove redundant spaces."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


resume_service = ResumeService()
