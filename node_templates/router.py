from fastapi import APIRouter, Request, Depends ,HTTPException, Header
from sqlalchemy import orm
from config.database import get_db
from .models import NodeTemplate
from models import Tenant
from typing import Optional

router = APIRouter()

@router.get('/node-templates/')
def read_nodetemps(request: Request, db: orm.Session = Depends(get_db)):
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        return HTTPException(status_code=400, detail="Tenant ID is missing in headers")
    if tenant_id == "demo":
        tenant_id = 'ai'

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    node_temps = db.query(NodeTemplate).filter(NodeTemplate.tenant_id == tenant_id).all()

    if not node_temps:
        raise HTTPException(status_code=404, detail="No contacts found for this tenant")

    return node_temps

@router.get("/node-templates/{node_template_id}/")
def get_node_temps(node_template_id : int, x_tenant_id: Optional[str] = Header(None)  ,db: orm.Session = Depends(get_db)):
    if not x_tenant_id:
        return HTTPException(500, detail="Tenant ID is missing")
    tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
    if not tenant:
        raise HTTPException(400, detail="Tenant Data not found")
    
    node_temp = db.query(NodeTemplate).filter(NodeTemplate.id == node_template_id).first()

    return node_temp

from fastapi import Body

@router.post("/flows/{id}")
def update_trigger_flow(
    id: int,
    data: dict = Body(...),
    db: orm.Session = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None),
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is missing")

    node_template = db.query(NodeTemplate).filter(
        NodeTemplate.id == id,
        NodeTemplate.tenant_id == x_tenant_id
    ).first()

    if not node_template:
        raise HTTPException(status_code=404, detail="NodeTemplate not found")

    node_template.trigger = data.get("trigger", node_template.trigger)

    db.commit()
    db.refresh(node_template)

    return {"message": f"{node_template.name} updated successfully", "data": {
        "id": node_template.id,
        "name": node_template.name,
        "trigger": node_template.trigger
    }}

@router.get("/flows/")
def get_flows_with_trigger(
    db: orm.Session = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None),
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is missing")

    node_templates = db.query(NodeTemplate).filter(
        NodeTemplate.tenant_id == x_tenant_id,
        NodeTemplate.trigger.isnot(None),           # filter where trigger is not None
        NodeTemplate.trigger != ""                   # optionally exclude empty string triggers
    ).all()

    if not node_templates:
        raise HTTPException(status_code=404, detail="No NodeTemplates with trigger found")

    return [
        {"id": nt.id, "name": nt.name, "trigger": nt.trigger} for nt in node_templates
    ]

@router.delete("/flows-delete/{node_template_id}/")
def delete_trigger_only(
    node_template_id: int,
    db: orm.Session = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is missing")

    node_template = db.query(NodeTemplate).filter(
        NodeTemplate.id == node_template_id,
        NodeTemplate.tenant_id == x_tenant_id
    ).first()

    if not node_template:
        raise HTTPException(status_code=404, detail="Flow not found")

    node_template.trigger = None
    db.commit()

    return {"message": f"Trigger for '{node_template.name}' cleared successfully"}