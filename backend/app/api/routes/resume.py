from fastapi import APIRouter, File, HTTPException, UploadFile, status
from backend.app.ai.resume_parser import resume_parser
from backend.app.models.resume import CandidateProfile, CandidateProfileUpdate, ResumeUploadResponse
from backend.app.services.resume_service import resume_service

router = APIRouter(prefix="/resume", tags=["Resume"])


@router.post("/upload", response_model=ResumeUploadResponse, status_code=status.HTTP_200_OK)
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume (PDF or DOCX), extract text, and parse into a structured CandidateProfile."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing in the uploaded file."
        )

    # 1. Validate file extension
    ext = resume_service.validate_file_extension(file.filename, file.content_type)

    # 2. Read file contents
    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded file: {str(e)}"
        )
    finally:
        await file.close()

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    # 3. Extract text from PDF or DOCX
    extracted_text = resume_service.extract_text(contents, ext)

    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No readable text could be extracted from the file."
        )

    # 4. Parse text into structured CandidateProfile
    profile = resume_parser.parse(extracted_text)

    # 5. Persist the current profile
    resume_service.save_profile(profile)

    return ResumeUploadResponse(
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(contents),
        extracted_text_length=len(extracted_text),
        profile=profile
    )


@router.get("/profile", response_model=CandidateProfile, status_code=status.HTTP_200_OK)
def get_candidate_profile():
    """Retrieve the currently parsed CandidateProfile."""
    profile = resume_service.get_current_profile()
    if not profile:
        # Return default initialized candidate profile if none has been uploaded yet
        return CandidateProfile()
    return profile


@router.patch("/profile", response_model=CandidateProfile, status_code=status.HTTP_200_OK)
def update_candidate_profile(update_data: CandidateProfileUpdate):
    """Update user preferences or profile fields (e.g. target roles, locations, match threshold)."""
    updated = resume_service.update_profile(update_data)
    return updated
