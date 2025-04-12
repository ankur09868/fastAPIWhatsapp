from fastapi import APIRouter, Request, Depends ,HTTPException, Header,status
from sqlalchemy import orm
from config.database import get_db
from typing import Optional
from models import Tenant
from .models import Catalog

router = APIRouter()

@router.post("/catalogid",  status_code=status.HTTP_201_CREATED)
async def create_catalog(request: Request, db: orm.Session = Depends(get_db)):
    try:
        # Extracting headers and body
        tenant_id = request.headers.get('X-Tenant-Id')
        body = await request.json()
        
        # Validate tenant ID
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing tenant ID header"
            )
        
        # Validate tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Validate required fields in body
        if 'catalog_id' not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="catalog_id is required"
            )
        
        if 'spreadsheet_link' not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="spreadsheet_link is required"
            )
        
        # Check if a catalog with this catalog_id already exists
        existing_catalog = db.query(Catalog).filter(
            Catalog.catalog_id == body['catalog_id']
        ).first()
        
        if existing_catalog:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A catalog with catalog_id {body['catalog_id']} already exists"
            )
        
        # Create new catalog
        new_catalog = Catalog(
            catalog_id=body['catalog_id'],
            spreadsheet_link=body['spreadsheet_link'],
            razorpay_key=body.get('razorpay_key'),  # Optional field
            tenant_id=tenant_id
        )
        
        db.add(new_catalog)
        db.commit()
        db.refresh(new_catalog)
        
        return new_catalog
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create catalog: {str(e)}"
        )

@router.put("/catalogid/{catalog_id}", status_code=status.HTTP_200_OK)
async def update_catalog(
    catalog_id: int,
    request: Request, 
    db: orm.Session = Depends(get_db)
):
    try:
        # Extracting headers and body
        tenant_id = request.headers.get('X-Tenant-Id')
        body = await request.json()
        
        # Validate tenant ID
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing tenant ID header"
            )
        
        # Validate tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Find the catalog by catalog_id and tenant_id
        catalog = db.query(Catalog).filter(
            Catalog.catalog_id == catalog_id,
            Catalog.tenant_id == tenant_id
        ).first()
        
        if not catalog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Catalog with catalog_id {catalog_id} not found for this tenant"
            )
        
        # Check if anything needs to be updated
        if 'spreadsheet_link' not in body and 'razorpay_key' not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field (spreadsheet_link or razorpay_key) must be provided for update"
            )
        
        # Update fields if provided
        if 'spreadsheet_link' in body:
            catalog.spreadsheet_link = body['spreadsheet_link']
            
        if 'razorpay_key' in body:
            catalog.razorpay_key = body['razorpay_key']
        
        # Save changes
        db.commit()
        db.refresh(catalog)
        
        return {
            "id": catalog.id,
            "catalog_id": catalog.catalog_id,
            "spreadsheet_link": catalog.spreadsheet_link,
            "razorpay_key": catalog.razorpay_key,
            "tenant_id": catalog.tenant_id,
            "message": "Catalog updated successfully"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update catalog: {str(e)}"
        )
    
@router.get("/catalogids", )
async def get_catalogs(
    request: Request,
    db: orm.Session = Depends(get_db)
):
    try:
        # Extracting tenant_id from header
        tenant_id = request.headers.get('X-Tenant-Id')
        
        # Validate tenant ID
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing tenant ID header"
            )
        
        # Validate tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Get catalogs for this tenant
        catalogs = db.query(Catalog).filter(Catalog.tenant_id == tenant_id).all()
        return catalogs
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get catalogs: {str(e)}"
        )