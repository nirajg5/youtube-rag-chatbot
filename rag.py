"""
YouTube RAG System
Handles transcript retrieval, embedding, and question answering.
"""

import os
import logging
from functools import lru_cache
from typing import Optional, List
from dotenv import load_dotenv

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "openai/gpt-4o-mini"

# Chunk configuration
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
RETRIEVAL_K = 4

# Headers for OpenRouter
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "HTTP-Referer": "http://localhost:8000",
    "X-Title": "YouTube RAG Chatbot",
}


class RAGException(Exception):
    """Custom exception for RAG-related errors"""
    pass


@lru_cache(maxsize=128)
def get_embeddings():
    """
    Get or create embeddings model (cached for reuse)
    """
    try:
        return OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            default_headers=HEADERS,
        )
    except Exception as e:
        logger.error(f"Failed to create embeddings model: {str(e)}")
        raise RAGException(f"Embeddings initialization failed: {str(e)}")


@lru_cache(maxsize=128)
def get_llm():
    """
    Get or create LLM instance (cached for reuse)
    """
    try:
        return ChatOpenAI(
            model=CHAT_MODEL,
            temperature=0.2,
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            default_headers=HEADERS,
            max_tokens=1000,
            timeout=30,
        )
    except Exception as e:
        logger.error(f"Failed to create LLM: {str(e)}")
        raise RAGException(f"LLM initialization failed: {str(e)}")


def fetch_transcript(video_id: str) -> str:
    """
    Fetch transcript from YouTube video
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Full transcript text
        
    Raises:
        RAGException: If transcript cannot be fetched
    """
    try:
        # Instantiate API (required in this environment)
        api = YouTubeTranscriptApi()
        
        try:
            # Try .list() method (returns TranscriptList or list of Transcripts)
            transcripts = api.list(video_id)
        except AttributeError:
             # Fallback if .list() fails, maybe static get_transcript exists? 
             # (Unlikely given tests, but safe fallback)
             transcripts = YouTubeTranscriptApi.get_transcript(video_id)
             # If get_transcript returns data directly, return it
             if isinstance(transcripts, list) and isinstance(transcripts[0], dict):
                 # It's already the data
                 transcript = " ".join(chunk["text"] for chunk in transcripts)
                 logger.info(f"✅ Transcript fetched successfully ({len(transcript)} chars)")
                 return transcript

        # Iterate to find suitable transcript
        transcript_obj = None
        
        # 1. Try built-in find_transcript (if available)
        if hasattr(transcripts, 'find_transcript'):
            try:
                transcript_obj = transcripts.find_transcript(['en'])
            except:
                pass
        
        # 2. Manual iteration for English
        if not transcript_obj:
            # Convert to list to iterate safely
            t_list = list(transcripts)
            
            # Prioritize manual English
            for t in t_list:
                if t.language_code == 'en' and not t.is_generated:
                    transcript_obj = t
                    break
            
            # Then generated English
            if not transcript_obj:
                for t in t_list:
                    if t.language_code.startswith('en'):
                        transcript_obj = t
                        break
            
            # Fallback to first available
            if not transcript_obj and t_list:
                transcript_obj = t_list[0]
        
        if not transcript_obj:
            raise RAGException("No suitable transcript found")
            
        # Fetch the actual data
        transcript_data = transcript_obj.fetch()
        
        # Combine all text chunks
        transcript = " ".join(chunk["text"] for chunk in transcript_data)
        
        logger.info(f"✅ Transcript fetched successfully ({len(transcript)} characters)")
        return transcript
        
    except TranscriptsDisabled:
        logger.error(f"Transcripts are disabled for video: {video_id}")
        raise RAGException(
            "Transcripts are disabled for this video. "
            "The video owner has disabled captions/transcripts."
        )
    except NoTranscriptFound:
        logger.error(f"No transcript found for video: {video_id}")
        raise RAGException(
            "No transcript available for this video. "
            "The video may not have captions enabled."
        )
    except Exception as e:
        logger.error(f"Error fetching transcript: {str(e)}")
        raise RAGException(f"Failed to fetch transcript: {str(e)}")


def create_chunks(transcript: str) -> List[Document]:
    """
    Split transcript into chunks for embedding
    
    Args:
        transcript: Full transcript text
        
    Returns:
        List of Document objects
    """
    try:
        logger.info("📄 Splitting transcript into chunks...")
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        docs = splitter.create_documents([transcript])
        
        logger.info(f"✅ Created {len(docs)} chunks")
        return docs
        
    except Exception as e:
        logger.error(f"Error creating chunks: {str(e)}")
        raise RAGException(f"Failed to create document chunks: {str(e)}")


def initialize_retriever(video_id: str):
    """
    Initialize RAG retriever for a YouTube video
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Retriever object or None if initialization fails
    """
    try:
        # Validate video ID
        if not video_id or len(video_id) != 11:
            logger.error(f"Invalid video ID: {video_id}")
            raise RAGException("Invalid video ID format")
        
        # Fetch transcript
        transcript = fetch_transcript(video_id)
        
        if not transcript or len(transcript) < 100:
            logger.error(f"Transcript too short: {len(transcript)} characters")
            raise RAGException("Transcript is too short or empty")
        
        # Create chunks
        docs = create_chunks(transcript)
        
        # Get embeddings model
        embeddings = get_embeddings()
        
        # Create vector store
        logger.info("🔢 Creating vector store...")
        vectorstore = FAISS.from_documents(docs, embeddings)
        
        # Create retriever
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": RETRIEVAL_K}
        )
        
        logger.info(f"✅ Retriever initialized successfully for video: {video_id}")
        return retriever
        
    except RAGException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in initialize_retriever: {str(e)}", exc_info=True)
        raise RAGException(f"Failed to initialize retriever: {str(e)}")


def get_answer(retriever, question: str, language: str = "English") -> str:
    """
    Get answer to a question using RAG
    
    Args:
        retriever: Initialized retriever object
        question: User's question
        language: Response language (default: English)
        
    Returns:
        Answer string
    """
    try:
        if retriever is None:
            return "Transcript unavailable for this video."
        
        if not question or len(question.strip()) == 0:
            return "Please provide a valid question."
        
        logger.info(f"🔍 Retrieving relevant documents for question: {question[:100]}...")
        
        # Retrieve relevant documents
        docs = retriever.get_relevant_documents(question)
        
        if not docs:
            logger.warning("No relevant documents found")
            return "I couldn't find relevant information in the transcript to answer your question."
        
        # Combine context from retrieved documents
        context = "\n\n".join(d.page_content for d in docs)
        
        logger.info(f"📝 Found {len(docs)} relevant chunks ({len(context)} characters)")
        
        # Create prompt
        prompt = PromptTemplate(
            template="""You are a helpful assistant answering questions about a YouTube video based on its transcript.

Instructions:
- Use ONLY the context provided below to answer the question
- Provide clear, concise, and accurate answers
- Reply in {language}
- If the answer is not in the context, say "I don't have enough information in the transcript to answer this question."
- Do not make up information or use external knowledge
- You can quote directly from the transcript when relevant

Context from video transcript:
{context}

Question: {question}

Answer:""",
            input_variables=["context", "question", "language"],
        )
        
        # Get LLM
        llm = get_llm()
        
        # Create chain
        chain = prompt | llm | StrOutputParser()
        
        logger.info("🤖 Generating answer...")
        
        # Get answer
        answer = chain.invoke({
            "context": context,
            "question": question,
            "language": language,
        })
        
        logger.info("✅ Answer generated successfully")
        return answer.strip()
        
    except Exception as e:
        logger.error(f"Error in get_answer: {str(e)}", exc_info=True)
        return f"An error occurred while generating the answer: {str(e)}"


def clear_cache():
    """Clear LRU caches for embeddings and LLM"""
    get_embeddings.cache_clear()
    get_llm.cache_clear()
    logger.info("🧹 Caches cleared")
