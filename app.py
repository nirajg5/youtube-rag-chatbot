"""
YouTube RAG Chatbot - FastAPI Backend
Provides endpoints for video ID management and question answering.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from rag import initialize_retriever, get_answer, RAGException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state management
class AppState:
    """Application state container"""
    def __init__(self):
        self.current_video_id: Optional[str] = None
        self.current_retriever = None
        self.initialization_in_progress: bool = False

app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app"""
    logger.info("🚀 YouTube RAG Chatbot starting up...")
    yield
    logger.info("🛑 YouTube RAG Chatbot shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="YouTube RAG Chatbot API",
    description="RAG-powered chatbot for YouTube video transcripts",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class VideoID(BaseModel):
    """Video ID model"""
    video_id: str = Field(..., min_length=11, max_length=11)
    
    @validator('video_id')
    def validate_video_id(cls, v):
        """Validate YouTube video ID format"""
        if not v.isalnum() and not all(c.isalnum() or c in '-_' for c in v):
            raise ValueError('Invalid YouTube video ID format')
        return v


class Query(BaseModel):
    """Query model for asking questions"""
    question: str = Field(..., min_length=1, max_length=1000)
    language: str = Field(default="English", max_length=50)


class VideoIDResponse(BaseModel):
    """Response model for video ID endpoint"""
    video_id: Optional[str]
    status: str
    is_initializing: bool = False


class AnswerResponse(BaseModel):
    """Response model for ask endpoint"""
    answer: str
    sources_used: int


class ErrorResponse(BaseModel):
    """Error response model"""
    detail: str
    error_code: str


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Routes
@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve the main index.html page"""
    return FileResponse("static/index.html")


@app.post(
    "/video-id",
    response_model=VideoIDResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid video ID"},
        500: {"model": ErrorResponse, "description": "Server error"}
    }
)
async def set_video_id(data: VideoID) -> VideoIDResponse:
    """
    Set the current video ID and initialize RAG retriever
    
    This endpoint:
    1. Updates the current video ID if changed
    2. Initializes the RAG retriever for the new video
    3. Returns the current status
    """
    try:
        # Check if video ID has changed
        if data.video_id == app_state.current_video_id:
            logger.info(f"Video ID unchanged: {data.video_id}")
            return VideoIDResponse(
                video_id=app_state.current_video_id,
                status="already_loaded"
            )
        
        # Prevent concurrent initialization
        if app_state.initialization_in_progress:
            logger.warning(f"Initialization already in progress")
            return VideoIDResponse(
                video_id=app_state.current_video_id,
                status="initializing",
                is_initializing=True
            )
        
        # Update state
        app_state.initialization_in_progress = True
        app_state.current_video_id = data.video_id
        
        logger.info(f"🎬 Initializing RAG for video: {data.video_id}")
        
        # Initialize retriever
        app_state.current_retriever = initialize_retriever(data.video_id)
        
        if app_state.current_retriever is None:
            logger.error(f"Failed to initialize retriever for video: {data.video_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not load transcript for this video. It may be disabled or unavailable."
            )
        
        logger.info(f"✅ Successfully initialized RAG for video: {data.video_id}")
        
        return VideoIDResponse(
            video_id=app_state.current_video_id,
            status="initialized"
        )
        
    except RAGException as e:
        logger.error(f"RAG error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in set_video_id: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the video"
        )
    finally:
        app_state.initialization_in_progress = False


@app.get(
    "/video-id",
    response_model=VideoIDResponse,
    status_code=status.HTTP_200_OK
)
async def get_video_id() -> VideoIDResponse:
    """Get the current video ID and initialization status"""
    return VideoIDResponse(
        video_id=app_state.current_video_id,
        status="loaded" if app_state.current_retriever else "not_loaded",
        is_initializing=app_state.initialization_in_progress
    )


@app.post(
    "/ask",
    response_model=AnswerResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    }
)
async def ask(data: Query) -> AnswerResponse:
    """
    Ask a question about the current video
    
    Requires a video to be loaded first via /video-id endpoint
    """
    try:
        # Check if retriever is ready
        if not app_state.current_retriever:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No video loaded. Please load a video first."
            )
        
        if app_state.initialization_in_progress:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Video is still initializing. Please wait a moment."
            )
        
        logger.info(f"💬 Processing question for video {app_state.current_video_id}: {data.question[:50]}...")
        
        # Get answer from RAG system
        answer = get_answer(
            retriever=app_state.current_retriever,
            question=data.question,
            language=data.language,
        )
        
        logger.info(f"✅ Answer generated successfully")
        
        return AnswerResponse(
            answer=answer,
            sources_used=4  # Default k value from retriever
        )
        
    except HTTPException:
        raise
    except RAGException as e:
        logger.error(f"RAG error in ask: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in ask: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the answer"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "video_loaded": app_state.current_video_id is not None,
        "retriever_ready": app_state.current_retriever is not None
    }


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
