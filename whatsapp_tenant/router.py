from fastapi import APIRouter, Request, Depends ,HTTPException, Header
from sqlalchemy import orm
from config.database import get_db
from .models import WhatsappTenantData, MessageStatus, BroadcastGroups, MessageStatistics, WhatsappChatIndividualMessageStatistics
from models import Tenant
from product.models import Product
from typing import Optional
from .schema import BroadcastGroupResponse, BroadcastGroupCreate,PromptUpdateRequest
from .crud import create_broadcast_group, get_broadcast_group, get_all_broadcast_groups
from typing import List, Optional
from contacts.models import Contact
from datetime import timedelta
router = APIRouter()

@router.get("/whatsapp_tenant/")
def get_whatsapp_tenant_data(x_tenant_id: Optional[str] = Header(None), bpid: Optional[str] = Header(None), db: orm.Session = Depends(get_db)):
    try:
        # Retrieve WhatsappTenantData for the specified tenant
        print("TENANT AND BPID:", x_tenant_id, bpid)

        if x_tenant_id:
            if x_tenant_id == "demo":
                x_tenant_id = 'ai'
            whatsapp_data = db.query(WhatsappTenantData).filter(WhatsappTenantData.tenant_id == x_tenant_id).order_by(WhatsappTenantData.id.asc()).all()
            if not whatsapp_data:
                raise HTTPException(status_code=404, detail="WhatsappTenantData not found for tenant")
            tenant_id = x_tenant_id
        elif bpid:
            whatsapp_data = db.query(WhatsappTenantData).filter(WhatsappTenantData.business_phone_number_id == bpid).all()
            if not whatsapp_data:
                raise HTTPException(status_code=404, detail="WhatsappTenantData not found for bpid")
            tenant_id = whatsapp_data[0].tenant_id
            # print("Tenant:", tenant_id)
            
        else:
            raise HTTPException(status_code=400, detail="Either Tenant-ID or BPID header must be provided")

        # catalog_data = db.query(Product).filter(Product.tenant_id == tenant_id).all()
        # print("catalog: ", catalog_data)
        tenantData = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        agents = tenantData.agents
        whatsapp_data.append({"agents": agents})
        return {
            "whatsapp_data": whatsapp_data
            # "catalog_data": catalog_data
        }
    
    except Exception as e:
        print("Error occurred with tenant:", x_tenant_id)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

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


from sqlalchemy.exc import IntegrityError

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

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

@router.post("/broadcast-groups/", response_model=BroadcastGroupResponse)
def create_group(request: BroadcastGroupCreate, db: orm.Session = Depends(get_db) , x_tenant_id : Optional[str] = Header(None)):
    try:
        members = [member.dict() for member in request.members]

        new_group = BroadcastGroups(
            id=request.id,  # You can generate the ID if not provided
            name=request.name,
            members=members,
            tenant_id = x_tenant_id
        )
        print("New Group: ", request.id, request.name, members)

        db.add(new_group)
        db.commit()
        db.refresh(new_group)

        
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