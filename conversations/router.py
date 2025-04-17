from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from config.database import get_db
from .models import Conversation
from models import Tenant
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import json
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
import logging
from functools import lru_cache

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for parallel decryption
thread_pool = ThreadPoolExecutor(max_workers=10)

# Simple in-memory cache using LRU cache decorator
# Set maxsize to the number of different conversation queries you expect to cache
conversation_cache = {}
CACHE_TTL = 60  # Cache TTL in seconds

def decrypt_data(encrypted_data: bytes, key: bytes):
    try:
        # Extract the IV from the first 16 bytes
        iv = encrypted_data[:16]
        encrypted_data = encrypted_data[16:]

        # Ensure the key is in bytes (handle memoryview if needed)
        if isinstance(key, memoryview):
            key = bytes(key)

        # Initialize the cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Perform decryption
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # Remove padding (PKCS#7 padding)
        pad_len = decrypted_data[-1]
        decrypted_data = decrypted_data[:-pad_len]

        return json.loads(decrypted_data.decode())
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        return None

def decrypt_message(encrypted_text, encryption_key):
    """Decrypt a message in a separate thread"""
    if encrypted_text is None:
        return None
    try:
        decrypted_text = decrypt_data(bytes(encrypted_text), key=encryption_key)
        if isinstance(decrypted_text, str):
            return decrypted_text
        elif decrypted_text:
            decrypted_str = json.dumps(decrypted_text)
            return decrypted_str.strip('"') if decrypted_str.startswith('"') else decrypted_str
        return None
    except Exception as e:
        logger.error(f"Message decryption error: {str(e)}")
        return None

def get_cache_key(contact_id, source, bpid, page_no):
    """Generate a cache key for the conversation query"""
    return f"{contact_id}:{source}:{bpid}:{page_no}"

def is_cache_valid(cache_entry):
    """Check if a cache entry is still valid"""
    if not cache_entry:
        return False
    return (time.time() - cache_entry['timestamp']) < CACHE_TTL

@router.get("/whatsapp_convo_get/{contact_id}")
async def view_conversation(
    contact_id: Optional[str],
    source: Optional[str] = Query(None),
    bpid: Optional[str] = Query(None),
    page_no: int = Query(1, ge=1),  # Ensure page_no is at least 1
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Get WhatsApp conversations for a contact with pagination.
    Optimized with parallel processing.
    """
    start_time = time.time()
    
    try:
        page_size = 50
        
        # Only select the key from tenant table
        tenant = db.query(Tenant.key).filter(Tenant.id == x_tenant_id).one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        encryption_key = tenant.key

        offset = (page_no - 1) * page_size

        # Base query for filtering conversations
        filter_conditions = [
            Conversation.contact_id == contact_id,
            Conversation.source == source
        ]
        
        # Add business phone number ID filter if provided
        if bpid:
            filter_conditions.append(Conversation.business_phone_number_id == bpid)

        # Get total count with a separate optimized query
        total_conversations = db.query(func.count(Conversation.id)).filter(*filter_conditions).scalar()
        
        # Fetch only necessary columns to reduce data transfer
        conversations = (
            db.query(
                Conversation.message_text,
                Conversation.encrypted_message_text, 
                Conversation.date_time,
                Conversation.sender
            )
            .filter(*filter_conditions)
            .order_by(Conversation.date_time.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        
        # Prepare data for parallel processing
        decrypt_tasks = []
        for i, conv in enumerate(conversations):
            if conv.encrypted_message_text is not None:
                # Add to tasks list for parallel processing
                decrypt_tasks.append((i, conv.encrypted_message_text, encryption_key))
            
        # Process decryption in parallel using thread pool
        decryption_results = {}
        if decrypt_tasks:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(
                    thread_pool, 
                    decrypt_message, 
                    task[1], 
                    task[2]
                ) for task in decrypt_tasks
            ]
            
            # Wait for all decryption tasks to complete
            results = await asyncio.gather(*futures)
            
            # Map results back to their conversation indexes
            for i, (idx, _, _) in enumerate(decrypt_tasks):
                decryption_results[idx] = results[i]
        
        # Format the conversations with decrypted messages
        formatted_conversations = []
        for i, conv in enumerate(reversed(conversations)):
            text_to_append = conv.message_text
            
            # Calculate the original index in the non-reversed list
            original_idx = len(conversations) - i - 1
            
            # Use decrypted text if available
            if original_idx in decryption_results and decryption_results[original_idx] is not None:
                text_to_append = decryption_results[original_idx]
                
            formatted_conversations.append({
                "text": text_to_append,
                "sender": conv.sender,
                "time": conv.date_time
            })

        total_pages = (total_conversations + page_size - 1) // page_size

        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Prepare response
        response = {
            "conversations": formatted_conversations,
            "page_no": page_no,
            "page_size": page_size,
            "total_conversations": total_conversations,
            "total_pages": total_pages,
            "processing_time_ms": round(processing_time * 1000, 2)  # For monitoring
        }
        
        return response

    except NoResultFound:
        raise HTTPException(status_code=404, detail="Data not found")
    except Exception as e:
        logger.error(f"Error in WhatsApp conversation retrieval: {str(e)}")
        raise HTTPException(status_code=500, detail="Error while fetching data")