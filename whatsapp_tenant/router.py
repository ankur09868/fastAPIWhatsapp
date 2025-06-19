from fastapi import APIRouter, Request, Depends ,HTTPException, Header, UploadFile, File, Form
from sqlalchemy import orm
from config.database import get_db
from .models import WhatsappTenantData, MessageStatus, BroadcastGroups, MessageStatistics, WhatsappChatIndividualMessageStatistics
from models import Tenant
from product.models import Product
from typing import Optional
from .schema import BroadcastGroupResponse, BroadcastGroupCreate,PromptUpdateRequest,BroadcastGroupContactDelete,BroadcastGroupAddContacts,BroadcastGroupMember
from .crud import create_broadcast_group, get_broadcast_group, get_all_broadcast_groups
from typing import List, Optional
from contacts.models import Contact
from datetime import timedelta
import requests
from uuid import uuid4  
from sqlalchemy.exc import IntegrityError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import httpx
import pandas as pd
from io import BytesIO
from uuid import uuid4
from node_templates.models import NodeTemplate
import json
from config.cache import custom_cache,get_cache,set_cache,CACHE_TTL,cache_lock  # <-- if you moved functions to cache.py

router = APIRouter()


@router.post("/reset-cache")
def reset_cache(bpid: str = Header(default=None)):
    if bpid:
        raise HTTPException(status_code=400, detail="Either X-Tenant-Id or bpid must be provided.")

    key = f"whatsapp_tenant:{bpid}"

    with cache_lock:
        if key in custom_cache:
            del custom_cache[key]
            return JSONResponse(content={"message": f"Cache cleared for key: {key}"})
        else:
            return JSONResponse(content={"message": f"No cache entry found for key: {key}"})

@router.get("/whatsapp_tenant")
def get_whatsapp_tenant_data(
    x_tenant_id: Optional[str] = Header(None),
    bpid: Optional[str] = Header(None),
    db: orm.Session = Depends(get_db)
):
    try:
        print("TENANT AND BPID:", x_tenant_id, bpid)

        # -----------------------------
        # 1. Resolve tenant_id and bpid
        # -----------------------------

        if x_tenant_id:
            if x_tenant_id == "demo":
                x_tenant_id = "ai"

            # Try getting BPID from cache
            bpid = get_cache(f"tenant_to_bpid:{x_tenant_id}")
            if not bpid:
                print("[CACHE MISS] tenant_to_bpid")
                record = db.query(WhatsappTenantData.business_phone_number_id)\
                           .filter(WhatsappTenantData.tenant_id == x_tenant_id)\
                           .order_by(WhatsappTenantData.id.asc())\
                           .first()
                if not record:
                    raise HTTPException(status_code=404, detail="BPID not found for tenant")

                bpid = str(record.business_phone_number_id)
                # Cache both directions
                set_cache(f"tenant_to_bpid:{x_tenant_id}", bpid)
                set_cache(f"bpid_to_tenant:{bpid}", x_tenant_id)

            tenant_id = x_tenant_id

        elif bpid:
            # Try getting tenant_id from cache
            tenant_id = get_cache(f"bpid_to_tenant:{bpid}")
            if not tenant_id:
                print("[CACHE MISS] bpid_to_tenant")
                record = db.query(WhatsappTenantData.tenant_id)\
                           .filter(WhatsappTenantData.business_phone_number_id == bpid)\
                           .first()
                if not record:
                    raise HTTPException(status_code=404, detail="Tenant ID not found for BPID")

                tenant_id = str(record.tenant_id)
                # Cache both directions
                set_cache(f"bpid_to_tenant:{bpid}", tenant_id)
                set_cache(f"tenant_to_bpid:{tenant_id}", bpid)

        else:
            raise HTTPException(status_code=400, detail="Either X-Tenant-Id or BPID header must be provided")

        # --------------------------------------
        # 2. Use bpid for main cache key always
        # --------------------------------------

        cache_key = f"whatsapp_tenant:{bpid}"
        cached_response = get_cache(cache_key)
        print("cache key", cache_key)
        if cached_response:
            print("[CACHE HIT] Returning cached response")
            return cached_response

        print(f"[CACHE MISS] Fetching full data for key: {cache_key}")

        # --------------------------------------
        # 3. Fetch main WhatsappTenantData data
        # --------------------------------------

        whatsapp_data = db.query(WhatsappTenantData)\
                          .filter(WhatsappTenantData.business_phone_number_id == bpid).all()
        if not whatsapp_data:
            raise HTTPException(status_code=404, detail="WhatsappTenantData not found")

        # --------------------------------------
        # 4. Fetch tenant, agents, triggers
        # --------------------------------------

        tenantData = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenantData:
            raise HTTPException(status_code=404, detail="Tenant not found")

        agents = tenantData.agents
        node_templates = db.query(NodeTemplate.id, NodeTemplate.name, NodeTemplate.trigger)\
                           .filter(NodeTemplate.tenant_id == tenant_id).all()

        node_template_data = [
            {"id": nt.id, "name": nt.name, "trigger": nt.trigger}
            for nt in node_templates if nt.trigger
        ]

        # --------------------------------------
        # 5. Build and cache response
        # --------------------------------------

        response_data = {
            "whatsapp_data": jsonable_encoder(whatsapp_data),
            "agents": jsonable_encoder(agents),
            "triggers": node_template_data
        }

        set_cache(cache_key, response_data)
        print(f"[CACHE SET] Key: {cache_key}, TTL: {CACHE_TTL}")

        return response_data

    except Exception as e:
        print("Error occurred with tenant:", x_tenant_id)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# @router.get("/whatsapp_tenant")
# def get_whatsapp_tenant_data(
#     x_tenant_id: Optional[str] = Header(None),
#     bpid: Optional[str] = Header(None),
#     db: orm.Session = Depends(get_db)
# ):
#     try:
#         print("TENANT AND BPID:", x_tenant_id, bpid)

#         # Cache key
#         cache_key = f"whatsapp_tenant:{x_tenant_id or bpid}"

#         # Check Redis cache first
#         cached_response = redis_client.get(cache_key)
#         if cached_response:
#             print("[CACHE HIT] Returning cached response")
#             return json.loads(cached_response)
#         print(f"[CACHE MISS] Fetching from DB for key: {cache_key}")
#         # --- original DB fetch logic below ---
#         if x_tenant_id:
#             if x_tenant_id == "demo":
#                 x_tenant_id = 'ai'
#             whatsapp_data = db.query(WhatsappTenantData)\
#                               .filter(WhatsappTenantData.tenant_id == x_tenant_id)\
#                               .order_by(WhatsappTenantData.id.asc()).all()
#             if not whatsapp_data:
#                 raise HTTPException(status_code=404, detail="WhatsappTenantData not found for tenant")
#             tenant_id = x_tenant_id

#         elif bpid:
#             whatsapp_data = db.query(WhatsappTenantData)\
#                               .filter(WhatsappTenantData.business_phone_number_id == bpid).all()
#             if not whatsapp_data:
#                 raise HTTPException(status_code=404, detail="WhatsappTenantData not found for bpid")
#             tenant_id = whatsapp_data[0].tenant_id

#         else:
#             raise HTTPException(status_code=400, detail="Either Tenant-ID or BPID header must be provided")

#         # Get tenant
#         tenantData = db.query(Tenant).filter(Tenant.id == tenant_id).first()
#         if not tenantData:
#             raise HTTPException(status_code=404, detail="Tenant not found")

#         agents = tenantData.agents

#         node_templates = db.query(NodeTemplate.id, NodeTemplate.name, NodeTemplate.trigger)\
#                            .filter(NodeTemplate.tenant_id == tenant_id).all()

#         node_template_data = [
#             {"id": nt.id, "name": nt.name, "trigger": nt.trigger}
#             for nt in node_templates if nt.trigger
#         ]

#         response_data = {
#             "whatsapp_data": jsonable_encoder(whatsapp_data),
#             "agents": jsonable_encoder(agents),
#             "triggers": node_template_data
#         }

#         # Cache the response in Redis for 5 minutes (300 seconds)
#         redis_client.setex(cache_key,300, json.dumps(response_data))
#         print(f"[CACHE SET] Cached response for key: {cache_key} with 300s TTL")

#         return response_data

#     except Exception as e:
#         print("Error occurred with tenant:", x_tenant_id)
#         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# @router.get("/whatsapp_tenant")
# def get_whatsapp_tenant_data(
#     x_tenant_id: Optional[str] = Header(None),
#     bpid: Optional[str] = Header(None),
#     db: orm.Session = Depends(get_db)
# ):
#     try:
#         print("TENANT AND BPID:", x_tenant_id, bpid)

#         if x_tenant_id:
#             if x_tenant_id == "demo":
#                 x_tenant_id = 'ai'
#             whatsapp_data = db.query(WhatsappTenantData)\
#                               .filter(WhatsappTenantData.tenant_id == x_tenant_id)\
#                               .order_by(WhatsappTenantData.id.asc()).all()
#             if not whatsapp_data:
#                 raise HTTPException(status_code=404, detail="WhatsappTenantData not found for tenant")
#             tenant_id = x_tenant_id

#         elif bpid:
#             whatsapp_data = db.query(WhatsappTenantData)\
#                               .filter(WhatsappTenantData.business_phone_number_id == bpid).all()
#             if not whatsapp_data:
#                 raise HTTPException(status_code=404, detail="WhatsappTenantData not found for bpid")
#             tenant_id = whatsapp_data[0].tenant_id

#         else:
#             raise HTTPException(status_code=400, detail="Either Tenant-ID or BPID header must be provided")

#         # Get tenant
#         tenantData = db.query(Tenant).filter(Tenant.id == tenant_id).first()
#         if not tenantData:
#             raise HTTPException(status_code=404, detail="Tenant not found")

#         # Get agents
#         agents = tenantData.agents

#         # Get relevant fields from NodeTemplate
#         node_templates = db.query(NodeTemplate.id, NodeTemplate.name, NodeTemplate.trigger)\
#                            .filter(NodeTemplate.tenant_id == tenant_id).all()

#         # Convert to list of dicts
#         node_template_data = [
#             {"id": nt.id, "name": nt.name, "trigger": nt.trigger}
#             for nt in node_templates if nt.trigger
#         ]
#         return {
#             "whatsapp_data": whatsapp_data,
#             "agents": agents,
#             "triggers": node_template_data
#         }

#     except Exception as e:
#         print("Error occurred with tenant:", x_tenant_id)
#         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.patch("/whatsapp_tenant/")
async def update_whatsapp_tenant_data(
    req: Request, 
    x_tenant_id: Optional[str] = Header(None), 
    db: orm.Session = Depends(get_db)
):
    try:
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="Tenant-ID header must be provided")
        
        
        # Retrieve the WhatsappTenantData for the specified tenant
        whatsapp_data = db.query(WhatsappTenantData).filter(WhatsappTenantData.tenant_id == x_tenant_id).all()
        
        if not whatsapp_data:
            raise HTTPException(status_code=404, detail="WhatsappTenantData not found for the given tenant")

        body = await req.json()

        # Update each field in the data payload
        for record in whatsapp_data:
            for key, value in body.items():
                if hasattr(record, key):  # Ensure the field exists
                    setattr(record, key, value)

        db.commit()  # Commit the changes to the database
        db.refresh(whatsapp_data[0])  # Refresh the first record to return updated data

        return {"message": "WhatsappTenantData updated successfully", "updated_data": [record for record in whatsapp_data]}

    except Exception as e:
        print(f"Error occurred while updating tenant data for {x_tenant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/refresh-status/")
def refresh_status(request: Request, db: orm.Session = Depends(get_db)):
    try:
        tenant_id = request.headers.get("X-Tenant-Id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Missing Tenant ID in headers")

        # Fetch all individual message statistics for this tenant
        individual_stats = db.query(WhatsappChatIndividualMessageStatistics).filter(
            WhatsappChatIndividualMessageStatistics.tenant_id == tenant_id
        ).all()

        # Group by message_id to handle multiple statuses for the same message
        message_status_map = {}
        for stat in individual_stats:
            if stat.message_id not in message_status_map:
                message_status_map[stat.message_id] = {
                    "template_name": stat.template_name or "Unknown",
                    "status": set(),  # Use a set to track all statuses
                    "timestamp": stat.timestamp,
                    "userPhone": stat.userPhone,
                    "type": stat.type
                }
            
            # Add this status to the set
            if stat.status:
                message_status_map[stat.message_id]["status"].add(stat.status)
            
            # Update template name if available
            if stat.template_name and not message_status_map[stat.message_id]["template_name"] == "Unknown":
                message_status_map[stat.message_id]["template_name"] = stat.template_name

        # Now process the consolidated message statuses
        template_stats = {}
        for message_id, data in message_status_map.items():
            template_name = data["template_name"]
            # Create a key using template name + date (YYYY-MM-DD)
            try:
                date_str = data["timestamp"].strftime("%Y-%m-%d") if data["timestamp"] else "unknown-date"
            except:
                date_str = "unknown-date"
                
            record_key = f"{template_name}_{date_str}"
            
            if record_key not in template_stats:
                template_stats[record_key] = {
                    "name": None,  # Group name (null if not available)
                    "delivered": 0,
                    "read": 0,
                    "replied": 0,
                    "failed": 0,
                    "template_name": template_name
                }
            
            # Convert set to list for JSON serialization
            status_list = list(data["status"]) if "status" in data else []
            
            # Count statuses (except sent - we'll calculate it later)
            if "delivered" in status_list:
                template_stats[record_key]["delivered"] += 1
            if "read" in status_list:
                template_stats[record_key]["read"] += 1
            if "failed" in status_list:
                template_stats[record_key]["failed"] += 1
                
            # For replies, we might need special logic
            if data.get("type") == "reply" or "replied" in status_list:
                template_stats[record_key]["replied"] += 1

        # Update or create records in MessageStatistics table
        updated_records = []
        for record_key, stats in template_stats.items():
            try:
                # Calculate sent as delivered + failed
                stats["sent"] = stats["delivered"] + stats["failed"]
                
                existing_record = db.query(MessageStatistics).filter(
                    MessageStatistics.tenant_id == tenant_id,
                    MessageStatistics.record_key == record_key
                ).first()

                if existing_record:
                    # Update existing record
                    existing_record.name = stats["name"]
                    existing_record.sent = stats["sent"]  # Now this is delivered + failed
                    existing_record.delivered = stats["delivered"]
                    existing_record.read = stats["read"]
                    existing_record.replied = stats["replied"]
                    existing_record.failed = stats["failed"]
                    existing_record.template_name = stats["template_name"]
                    updated_records.append(record_key)
                else:
                    # Create a new record
                    new_record = MessageStatistics(
                        tenant_id=tenant_id,
                        record_key=record_key,
                        name=stats["name"],
                        sent=stats["sent"],  # Now this is delivered + failed
                        delivered=stats["delivered"],
                        read=stats["read"],
                        replied=stats["replied"],
                        failed=stats["failed"],
                        template_name=stats["template_name"]
                    )
                    db.add(new_record)
                    updated_records.append(record_key)
            except Exception as e:
                print(f"Error processing record {record_key}: {str(e)}")
                # Continue with other records

        # Commit changes to the database
        db.commit()
        
        # Use jsonable_encoder to properly handle all types
        response_data = {
            "message": "Message statistics updated successfully",
            "updated_records": len(updated_records)
        }
        
        return JSONResponse(content=jsonable_encoder(response_data))

    except IntegrityError as e:
        db.rollback()
        print(f"IntegrityError: {e}")
        error_msg = f"Database integrity error: {str(e)}"
        return JSONResponse(
            content=jsonable_encoder({"detail": error_msg}),
            status_code=400
        )
    except Exception as e:
        db.rollback()
        print(f"Unexpected error: {e}")
        error_msg = f"An unexpected error occurred: {str(e)}"
        return JSONResponse(
            content=jsonable_encoder({"detail": error_msg}),
            status_code=500
        )

@router.get("/get-status/")
def get_status( request: Request, db: orm.Session = Depends(get_db)):
    """
    Retrieve all records from the message_statistics table without a response model.
    """
    try:
        # Fetch all records
        tenant_id = request.headers.get("X-Tenant-Id")
        # whatsapp_data = db.query(WhatsappTenantData).filter(WhatsappTenantData.tenant_id == tenant_id).all()

        records = db.query(MessageStatistics).filter(MessageStatistics.tenant_id == tenant_id)


        # Convert SQLAlchemy objects into dictionaries for JSON serialization
        result = [
            {
                "id": record.id,
                "record_key": record.record_key,
                "name": record.name,
                "sent": record.sent,
                "delivered": record.delivered,
                "read": record.read,
                "replied": record.replied,
                "failed": record.failed,
                "template_name": record.template_name,
            }
            for record in records
        ]
        return transform_data(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")

def transform_data(input_list):
    
    output = {}
    for item in input_list:
        
        key = item.pop("record_key")
        item.pop("id")
        output[key] = item

    return output

@router.post("/set-status/")
async def set_status(request: Request, db: orm.Session =Depends(get_db)):
    try:
        data = await request.json()

        business_phone_number_id = data.get("business_phone_number_id")
        user_phone_number = data.get("user_phone_number")
        broadcast_group = data.get("broadcast_group")

        message_status = db.query(MessageStatus).filter(
            MessageStatus.business_phone_number_id == business_phone_number_id,
            MessageStatus.user_phone_number == user_phone_number,
            MessageStatus.broadcast_group == broadcast_group
        ).first()

        if not message_status:
            message_status = MessageStatus(
                business_phone_number_id=business_phone_number_id,
                user_phone_number=user_phone_number,
                broadcast_group=broadcast_group,
                broadcast_group_name=data.get("broadcast_group_name"),
                sent=0,
                delivered=0,
                read=0,
                replied=0,
                failed=0,
            )
            db.add(message_status)

        for key in ["sent", "delivered", "read", "replied", "failed"]:
            if key in data and isinstance(data[key], bool):  # Check if key exists and is boolean
                if data[key]:
                    setattr(message_status, key, getattr(message_status, key, 0) + 1)
                else:
                    setattr(message_status, key, max(getattr(message_status, key, 0) - 1, 0))

        
        db.commit()
        db.refresh(message_status)

        return {"message": "Status updated successfully", "data": message_status}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred") from e
    
async def create_group_logic(request: BroadcastGroupCreate, db, x_tenant_id):
    members = [member.dict() for member in request.members]
    group_id = request.id or str(uuid4())
    new_group = BroadcastGroups(
        id=group_id,
        name=request.name,
        members=members,
        tenant_id=x_tenant_id
    )

    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    # await trigger_webhook_async(new_group, x_tenant_id)

    return new_group

# # 🔔 Webhook trigger function
# async def trigger_webhook_async(group, tenant_id):
#     try:
#         async with httpx.AsyncClient() as client:
#             await client.post(
#                 "https://nurenaiautomatic-b7hmdnb4fzbpbtbh.canadacentral-01.azurewebsites.net/webhook/template_status",
#                 json={
#                     "id": group.id,
#                     "name": group.name,
#                     "members": group.members,
#                     "tenant_id": tenant_id
#                 },
#                 headers={"Content-Type": "application/json"}
#             )
#     except Exception as e:
#         print("Webhook async failed", str(e))

@router.post("/broadcast-groups/", response_model=BroadcastGroupResponse)
async def create_group(request: BroadcastGroupCreate, db: orm.Session = Depends(get_db) , x_tenant_id : Optional[str] = Header(None)):
    try:
        new_group = await create_group_logic(request, db, x_tenant_id)
        return BroadcastGroupResponse(
            id=new_group.id,
            name=new_group.name,
            members=new_group.members,
            tenant_id = x_tenant_id
        )

    except Exception as e:
        db.rollback()
        print("Error creating groups: ", str(e))
        raise HTTPException(status_code=400, detail="Error in post: creating the broadcast group") from e

@router.get("/broadcast-groups/", response_model=List[BroadcastGroupResponse])
def get_groups(db: orm.Session = Depends(get_db), x_tenant_id : Optional[str] = Header(None)):
    try:
        groups = get_all_broadcast_groups( x_tenant_id,db=db)
        return groups
    except Exception as e:
        raise HTTPException(status_code=400, detail="Error fetching the broadcast groups") from e


@router.get("/broadcast-groups/{group_id}/", response_model=BroadcastGroupResponse)
def get_group(group_id: str, db: orm.Session = Depends(get_db)):
    try:
        
        group = get_broadcast_group(db=db, group_id=group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="Broadcast group not found")
        return group
    except Exception as e:
        raise HTTPException(status_code=400, detail="Error fetching the broadcast group") from e

@router.delete("/broadcast-groups/{group_id}/", response_model=dict)
def delete_group(group_id: str, db: orm.Session = Depends(get_db), x_tenant_id: Optional[str] = Header(None)):
    try:
        # Fetch the group to check existence and tenant ownership
        group = db.query(BroadcastGroups).filter(
            BroadcastGroups.id == group_id, 
            BroadcastGroups.tenant_id == x_tenant_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=404, 
                detail="Broadcast group not found or does not belong to the tenant"
            )
        
        # Delete the group
        db.delete(group)
        db.commit()
        
        return {"message": "Broadcast group deleted successfully"}
    
    except Exception as e:
        db.rollback()
        print("Error deleting group:", str(e))
        raise HTTPException(status_code=400, detail="Error deleting the broadcast group") from e

# Add new contact to broadcast group directly
@router.post("/broadcast-groups/add-contacts/")
async def create_contact_and_add_to_group(
    payload: BroadcastGroupAddContacts,
    request: Request,
    db: orm.Session = Depends(get_db)
):
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")

    created_contacts = []
    skipped_contacts = []

    # ✅ Step 1: Deduplicate contacts by phone number
    unique_contacts_dict = {contact.phone: contact for contact in payload.contacts}
    payload.contacts = list(unique_contacts_dict.values())

    # ✅ Step 2: Create contacts (no prior check)
    for contact in payload.contacts:
        contact_payload = {
            "phone": contact.phone,
            "name": contact.name,
            "tenant": tenant_id
        }

        try:
            res = requests.post(
                "https://backeng4whatsapp-dxbmgpakhzf9bped.centralindia-01.azurewebsites.net/contacts/",
                json=contact_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Tenant-Id": tenant_id
                }
            )
            if res.status_code == 201:
                created_contacts.append(contact.phone)
            else:
                # Contact might already exist or failed to create
                skipped_contacts.append({
                    "phone": contact.phone,
                    "reason": res.text
                })
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Contact creation failed: {str(e)}")

    # ✅ Step 3: Add all deduplicated contacts to group
    response = await add_contacts_to_group(payload, request, db)

    response["created_contacts"] = created_contacts
    response["skipped_contacts"] = skipped_contacts

    return response


@router.post("/broadcast-groups/excel/")
async def upload_and_add_contacts(
    request: Request,
    db: orm.Session = Depends(get_db),
    file: UploadFile = File(...),
    name: str = Form(...),
    model_name: str = Form("Contact"),
    x_tenant_id: Optional[str] = Header(None),
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")

    # Step 1: Read file content
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Step 2: Upload to external API (optional)
    try:
        files = {"file": (file.filename, file_bytes, file.content_type)}
        data = {"model_name": model_name}
        response = requests.post(
            "https://backeng4whatsapp-dxbmgpakhzf9bped.centralindia-01.azurewebsites.net/upload/",
            data=data,
            files=files,
            headers={"X-Tenant-Id": x_tenant_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Upload failed: {response.text}")
        if "Contacts are being uploaded" not in response.json().get("success", ""):
            raise HTTPException(status_code=400, detail="Unexpected response from upload service")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Step 3: Parse Excel
    try:
        df = pd.read_excel(BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {str(e)}")

    df.columns = [col.strip().lower() for col in df.columns]
    contact_models = []

    for _, row in df.iterrows():
        raw_phone = str(row.get("phone", "")).strip()
        contact_name = str(row.get("name", "")).strip() if "name" in df.columns else ""
        final_phone = None

        if raw_phone.isdigit():
            if len(raw_phone) == 12 and raw_phone.startswith("91"):
                final_phone = raw_phone
            elif len(raw_phone) == 10:
                final_phone = f"91{raw_phone}"

        if final_phone:
            contact_models.append(BroadcastGroupMember(phone=final_phone, name=contact_name or final_phone))

    if not contact_models:
        raise HTTPException(status_code=400, detail="No valid phone numbers found.")

    # Step 4: Create new group locally
    group_id = str(uuid4())
    group_create_payload = BroadcastGroupCreate(
        id=group_id,
        name=name,
        members=contact_models
    )

    try:
        new_group = await create_group_logic(group_create_payload, db, x_tenant_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create group: {str(e)}")

    
    # ✅ Final response
    return {
        "message": "Contacts uploaded and group created successfully.",
        "group_id": new_group.id,
        "group_name": new_group.name,
        "total_contacts_added": len(contact_models),
        "contacts": [contact.phone for contact in contact_models]
    }


@router.post("/")
async def add_contacts_to_group(
    payload: BroadcastGroupAddContacts,
    request: Request,
    db: orm.Session = Depends(get_db)
):
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id")

    group = db.query(BroadcastGroups).filter(
        BroadcastGroups.name == payload.groupName,
        BroadcastGroups.tenant_id == tenant_id
    ).first()

    if not group:
        raise HTTPException(status_code=404, detail="Broadcast group not found")

    existing_members = group.members or []
    existing_phones = {str(member["phone"]) for member in existing_members}

    new_contacts = [
        {"phone": contact.phone, "name": contact.name or str(contact.phone)}
        for contact in payload.contacts
        if str(contact.phone) not in existing_phones
    ]

    if not new_contacts:
        raise HTTPException(status_code=400, detail="No new contacts to add")

    group.members = existing_members + new_contacts
    db.commit()

    return {
        "message": "Contacts added successfully",
        "addedContacts": new_contacts,
        "totalMembers": group.members
    }

#delete contact from group 
@router.delete("/broadcast-group/delete-contact/")
async def delete_contact_from_group(
    payload: BroadcastGroupContactDelete,
    request: Request,
    db: orm.Session = Depends(get_db)
):
    tenant_id = request.headers.get("X-Tenant-Id")

    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")

    # Get the group based on name and tenant ID
    group = db.query(BroadcastGroups).filter(
        BroadcastGroups.name == payload.groupName,
        BroadcastGroups.tenant_id == tenant_id
    ).first()

    if not group:
        raise HTTPException(status_code=404, detail="Broadcast group not found")

    original_members = group.members or []

    # Filter out the contact with the given phone
    updated_members = [
        member for member in original_members
        if str(member.get("phone")) != str(payload.contactPhone)
    ]

    # If no contact was removed, it means contact was not in group
    if len(original_members) == len(updated_members):
        raise HTTPException(status_code=404, detail="Contact not found in group")

    # Update and save
    group.members = updated_members
    db.commit()

    return {
        "message": "Contact deleted successfully",
        "groupName": payload.groupName,
        "remainingMembers": updated_members
    }

@router.post("/message-statistics/")
@router.patch("/message-statistics/")
def create_or_update_message_statistics(name: str, tenant_id: str, data: dict, db: orm.Session = Depends(get_db)):
    """
    Creates a new entry or updates an existing one in the `message_statistics` table.

    Args:
        name (str): The name of the message statistics.
        tenant_id (str): The tenant ID associated with the statistics.
        data (dict): Dictionary containing the fields to update or create.
        db (Session): SQLAlchemy database session.

    Returns:
        dict: A dictionary containing the created/updated message statistics.
    """
    try:
        entry = db.query(MessageStatistics).filter_by(name=name, tenant_id=tenant_id).first()

        if entry:
            for key, value in data.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return {"message": "Entry updated successfully", "data": entry}
        else:
            new_entry = MessageStatistics(name=name, tenant_id=tenant_id, **data)
            db.add(new_entry)
            db.commit()
            db.refresh(new_entry)
            return {"message": "Entry created successfully", "data": new_entry}

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Integrity error. Please check the provided data.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.get("/prompt/fetch/")
def get_whatsapp_prompt(
    x_tenant_id: Optional[str] = Header(None),
    db: orm.Session = Depends(get_db)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")

    tenant_data = db.query(WhatsappTenantData).filter_by(tenant_id=x_tenant_id).first()

    if not tenant_data:
        raise HTTPException(status_code=404, detail="Tenant data not found")

    return {"tenant_id": x_tenant_id, "prompt": tenant_data.prompt}


@router.post("/prompt/create/")
def create_whatsapp_prompt(
    data: PromptUpdateRequest,
    x_tenant_id: Optional[str] = Header(None),
    db: orm.Session = Depends(get_db)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")

    tenant_data = db.query(WhatsappTenantData).filter_by(tenant_id=x_tenant_id).first()

    if not tenant_data:
        raise HTTPException(status_code=404, detail="Tenant data not found")

    if tenant_data.prompt:
        raise HTTPException(status_code=400, detail="Prompt already exists. Use PATCH to update.")

    tenant_data.prompt = data.prompt
    db.commit()

    return {"tenant_id": x_tenant_id, "prompt": tenant_data.prompt, "message": "Prompt added successfully"}


@router.patch("/prompt/edit/")
def update_whatsapp_prompt(
    data: PromptUpdateRequest,
    x_tenant_id: Optional[str] = Header(None),
    db: orm.Session = Depends(get_db)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")

    tenant_data = db.query(WhatsappTenantData).filter_by(tenant_id=x_tenant_id).first()

    if not tenant_data:
        raise HTTPException(status_code=404, detail="Tenant data not found")

    tenant_data.prompt = data.prompt
    db.commit()

    return {"tenant_id": x_tenant_id, "prompt": tenant_data.prompt, "message": "Prompt updated successfully"}


@router.delete("/prompt/delete/")
def delete_whatsapp_prompt(
    x_tenant_id: Optional[str] = Header(None),
    db: orm.Session = Depends(get_db)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")

    tenant_data = db.query(WhatsappTenantData).filter_by(tenant_id=x_tenant_id).first()

    if not tenant_data:
        raise HTTPException(status_code=404, detail="Tenant data not found")

    if not tenant_data.prompt:
        raise HTTPException(status_code=404, detail="No prompt to delete")

    tenant_data.prompt = None
    db.commit()

    return {"tenant_id": x_tenant_id, "message": "Prompt deleted successfully"}


@router.get("/tenants/ids")
def get_all_tenant_ids( db: orm.Session = Depends(get_db)):
    tenant_ids = db.query(Tenant.id).all()
    return {"tenant_ids": [tenant_id[0] for tenant_id in tenant_ids]}
