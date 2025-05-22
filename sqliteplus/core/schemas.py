from pydantic import BaseModel
from typing import Dict

class CreateTableSchema(BaseModel):
    columns: Dict[str, str]

class InsertDataSchema(BaseModel):
    msg: str
