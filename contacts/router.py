from fastapi import APIRouter, Request, Depends ,HTTPException, responses
from sqlalchemy import orm, or_, and_, text, nulls_first, nulls_last
from config.database import get_db
from .models import Contact
from whatsapp_tenant.models import WhatsappTenantData
from typing import Optional
from datetime import datetime, timedelta
import math

router = APIRouter()

@router.get("/contacts/filter/{page_no}")
def get_filtered_contacts(
    request: Request,
    page_no: int = 1,
    engagement_type: Optional[str] = None,
    contact_type: Optional[str] = None,
    sort_by: Optional[str] = None,
    db: orm.Session = Depends(get_db)
    ):
        
    try:
        tenant_id = request.headers.get("X-Tenant-Id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID missing in headers")

        today = datetime.now()
        contacts_query = db.query(Contact).filter(Contact.tenant_id == tenant_id)

        if engagement_type == "high":
            delivered = today - timedelta(days=3)
            replied = today - timedelta(days=7)
            contacts_query = contacts_query.filter(Contact.last_delivered >= delivered, Contact.last_replied >= replied)
        
        elif engagement_type == "medium":
            seen = today - timedelta(days=30)
            delivered = today - timedelta(days=14)
            contacts_query = contacts_query.filter(Contact.last_seen >= seen, Contact.last_delivered >= delivered)
        
        elif engagement_type == "low":
            created = today - timedelta(days=90)
            not_seen = today - timedelta(days=60)
            contacts_query = contacts_query.filter(Contact.createdOn >= created, or_(Contact.last_seen <= not_seen, Contact.last_seen.is_(None)))
        
        elif contact_type == "fresh":
            created = today - timedelta(days=14)
            contacts_query = contacts_query.filter(Contact.createdOn >= created, Contact.last_delivered == None)
        
        elif contact_type == "dormant":
            not_deli = today - timedelta(days=30)
            contacts_query = contacts_query.filter(or_(Contact.last_delivered <= not_deli, Contact.last_delivered.is_(None)))
        
        elif contact_type == "last_replied":
            replied = today - timedelta(days=7)
            contacts_query = contacts_query.filter(Contact.last_replied >= replied).order_by(Contact.last_replied.desc())

        page_size = 50  # Number of contacts per page

        if sort_by:
            contacts_query = contacts_query.order_by(getattr(Contact, sort_by).desc())

        total_contacts = contacts_query.count()
        total_pages = (total_contacts + page_size - 1) // page_size
        offset = page_size * (page_no - 1)

        contacts = contacts_query.offset(offset).limit(page_size).all()

        return {
            "contacts": contacts,
            "page_no": page_no,
            "page_size": page_size,
            "total_contacts": total_contacts,
            "total_pages": total_pages,
        }
    except Exception as e:
        print("Exception Occured: ", str(e))
        raise HTTPException(status_code=500, detail=f"An Error Occured: {str(e)}")

@router.get("/contacts")
def read_contacts(request: Request, db: orm.Session = Depends(get_db)):
    # Extract tenant_id from request headers
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID missing in headers")


    contacts = db.query(Contact).filter(Contact.tenant_id == tenant_id).order_by(Contact.id.asc()).all()
    
    if not contacts:
        raise HTTPException(status_code=404, detail="No contacts found for this tenant")

    return contacts

from sqlalchemy import func
@router.get("/contacts/{page_no}") 
def get_limited_contacts(
    req: Request,
    page_no: int = 1,
    phone: Optional[str] = None,
    order_by: Optional[str] = "id",
    sort_by: Optional[str] = "asc",
    db: orm.Session = Depends(get_db),
):
    
    tenant_id = req.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID missing in headers")

    page_size = 300  # Number of contacts per page
    
    # If phone parameter is provided, return only that contact
    if phone:
        # First find the contact with the given phone number
        contact = db.query(Contact).filter(
            Contact.tenant_id == tenant_id,
            Contact.phone == phone
        ).first()
        
        if contact is None:
            raise HTTPException(status_code=404, detail=f"Contact not found with phone {phone}")
        
        # Calculate which page this contact would be on
        if order_by == "id" and sort_by == "asc":  # For default sorting
            # Count how many contacts come before this one
            position = db.query(func.count(Contact.id)).filter(
                Contact.tenant_id == tenant_id,
                Contact.id < contact.id
            ).scalar()
            
            # Calculate page number
            page_no = (position // page_size) + 1
        else:
            # For other sorting, we need a different approach
            # Use the original SQL approach to find position
            order_expr = getattr(Contact, order_by)
            order_expr = order_expr.desc() if sort_by == "desc" else order_expr.asc()
            
            subquery = db.query(
                Contact,
                func.row_number().over(order_by=order_expr).label('row_num')
            ).filter(Contact.tenant_id == tenant_id).subquery()
            
            result = db.query(subquery.c.row_num).filter(
                subquery.c.id == contact.id
            ).scalar()
            
            page_no = math.ceil(result / page_size)
        
        # Return only the matching contact
        total_contacts = db.query(Contact).filter(Contact.tenant_id == tenant_id).count()
        total_pages = (total_contacts + page_size - 1) // page_size
        
        return {
            "contacts": [contact],  # Return only the matching contact in a list
            "page_no": page_no,
            "page_size": page_size,
            "total_contacts": 1,  # Only one contact is returned
            "total_pages": total_pages,
        }
    
    # Regular pagination logic (unchanged)
    offset = page_size * (page_no - 1)
    
    total_contacts = db.query(Contact).filter(Contact.tenant_id == tenant_id).count()
    total_pages = (total_contacts + page_size - 1) // page_size 

    order_by_clause = nulls_last(getattr(Contact, order_by).desc()) if sort_by == "desc" else nulls_last(getattr(Contact, order_by).asc())
    contacts = (
        db.query(Contact)
        .filter(Contact.tenant_id == tenant_id)
        .order_by(order_by_clause)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "contacts": contacts,
        "page_no": page_no,
        "page_size": page_size,
        "total_contacts": len(contacts),
        "total_pages": total_pages,
    }

# @router.get("/contacts/{page_no}") 
# def get_limited_contacts(
#     req: Request,
#     page_no: int = 1,
#     phone: Optional[str] = None,
#     order_by: Optional[str] = "id",
#     sort_by: Optional[str] = "asc",
#     db: orm.Session = Depends(get_db),
# ):
    
#     tenant_id = req.headers.get("X-Tenant-Id")
#     if not tenant_id:
#         raise HTTPException(status_code=400, detail="Tenant ID missing in headers")

#     if phone:
#         sql_query = text("""
#             SELECT *
#             FROM (
#                 SELECT 
#                     ROW_NUMBER() OVER (ORDER BY id) AS row_num, *
#                 FROM 
#                     contacts_contact
#                 WHERE tenant_id = :tenant
#             ) AS subquery_result
#             WHERE 
#                 phone = :phone;
#         """)
        
#         result = db.execute(sql_query, {"phone": phone, "tenant": tenant_id}).fetchone()

#         if result is None:
#             raise HTTPException(status_code=404, detail=f"Contact not found with phone {phone}")
#         # print("Result ", result)
#         page_no = math.ceil(result[0] / 50 )
        
#     page_size = 300  # Number of contacts per page
#     offset = page_size * (page_no - 1)
    
#     total_contacts = db.query(Contact).filter(Contact.tenant_id == tenant_id).count()

#     total_pages = (total_contacts + page_size - 1) // page_size 

#     order_by_clause = nulls_last(getattr(Contact, order_by).desc()) if sort_by == "desc" else nulls_last(getattr(Contact, order_by).asc())
#     contacts = (
#         db.query(Contact)
#         .filter(Contact.tenant_id == tenant_id)
#         .order_by(order_by_clause)
#         .offset(offset)
#         .limit(page_size)
#         .all()
#     )

#     return {
#         "contacts": contacts,
#         "page_no": page_no or None,
#         "page_size": page_size or None,
#         "total_contacts": len(contacts),
#         "total_pages": total_pages or None,
#     }

@router.patch("/contacts/")
async def update_contact(request: Request, db: orm.Session = Depends(get_db)):
    body = await request.json()  # Parse JSON request body
    contacts = body.get('contact_id', [])
    bg_id = body.get('bgId')
    bg_name = body.get('name')
    errors = []

    for contact_id in contacts:
        try:
            contact = db.query(Contact).filter(Contact.id == contact_id).first()
            if not contact:
                errors.append(f"Contact with id {contact_id} does not exist.")
                continue

            contact.bg_id = bg_id
            contact.bg_name = bg_name

            db.add(contact)
            db.commit()


        except Exception as e:
            db.rollback()
            errors.append(f"Error updating contact {contact_id}: {str(e)}")

    if errors:
        raise HTTPException(500, detail=errors)
    else:
        return responses.JSONResponse(content=None, status_code=200)
        
@router.delete("/contacts/")
async def delete_contacts(request: Request, db: orm.Session = Depends(get_db)):
    body = await request.json()  # Parse JSON request body
    contact_ids = body.get('contact_ids', [])  # List of contact IDs to delete
    errors = []

    # Extract tenant_id from request headers
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID missing in headers")


    for contact_id in contact_ids:
        try:
            # Fetch contact by ID
            contact = db.query(Contact).filter(Contact.id == contact_id, Contact.tenant_id == tenant_id).first()

            # If contact doesn't exist, add an error message
            if not contact:
                errors.append(f"Contact with id {contact_id} does not exist for tenant {tenant_id}.")
                continue

            # Delete the contact
            db.delete(contact)
            db.commit()

        except Exception as e:
            db.rollback()
            errors.append(f"Error deleting contact {contact_id}: {str(e)}")

    if errors:
        raise HTTPException(status_code=500, detail=errors)
    else:
        return responses.JSONResponse(content={"message": "Contacts deleted successfully."}, status_code=200)
        
@router.delete("/contacts/{contact_id}/", status_code=204)
def delete_contact(contact_id: int, request: Request, db: orm.Session = Depends(get_db)):
    # Extract tenant_id from request headers
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID missing in headers")

    # Fetch the contact by ID and tenant ID
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.tenant_id == tenant_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found for this tenant")

    # Delete the contact
    db.delete(contact)
    db.commit()

    return {"message": "Contact deleted successfully"}

@router.get("/contact")
def get_contact(phone: str, request: Request, db: orm.Session = Depends(get_db)):
    # Extract tenant_id from request headers
    tenant_id = request.headers.get("X-Tenant-Id")
    
    bpid = request.headers.get('bpid')
    print(tenant_id)
    print(bpid)
    if not tenant_id and not bpid:
        raise HTTPException(status_code=400, detail="Atleast one of tenant id or bpid must be provided")
    
    if(bpid):
        bpid_data = db.query(WhatsappTenantData).filter(WhatsappTenantData.business_phone_number_id == bpid).first()
        tenant_id = bpid_data.tenant_id

    contact = db.query(Contact).filter(Contact.phone == phone, Contact.tenant_id == tenant_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found for this tenant")

    return contact
