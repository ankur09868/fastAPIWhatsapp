from fastapi import APIRouter, Request, Depends ,HTTPException, Header
from sqlalchemy import orm, exc, Table, MetaData
from config.database import get_db
from .models import DynamicField, DynamicModel
from models import Base

router = APIRouter()

@router.get("/dynamic-models/")
def get_dynamic_model( request: Request , db: orm.Session = Depends(get_db)):
    response_data =[]
    tenant_id = request.headers.get('X-Tenant-Id')
    # print(tenant_id)
    
    dynamic_models = db.query(DynamicModel).filter(DynamicModel.tenant_id == tenant_id).all()

    # print(dynamic_models)
    for dynamic_model in dynamic_models:
        try:
            # print(dynamic_model.id)
            # fields = db.query(DynamicField).filter(DynamicField.dynamic_model_id == dynamic_model.id).all()
            # fields_data = [{'field_name': field.field_name , 'field_type': field.field_type} for field in fields]

            model_data = {
                    'model_name': dynamic_model.model_name,
                    # 'fields': fields_data
                }
            response_data.append(model_data)
        except Exception as e:
            return HTTPException(500, detail=f"Exception occured in get-dynamic-model: {str(e)}")
    # print("Response Data: ", response_data)
    return response_data

@router.get("/dynamic-models/{model_name}/")
def get_dynamic_model_data(model_name: str, db: orm.Session = Depends(get_db)):
    try:
        # print("Databsse Bind URL: ", db.bind)
        table_name = f"dynamic_entities_{model_name}"

        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=db.bind)


        query = db.execute(table.select()).fetchall()

        results = [dict(row._mapping) for row in query]
        return results
    
    except Exception as e:
        print("Exception occured: ", str(e))
        raise HTTPException(500, detail=f"An exception occured: {str(e)}")