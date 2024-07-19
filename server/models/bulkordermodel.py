from pydantic import BaseModel, conint, constr
from typing import List, Dict

class BulkOrderRequest(BaseModel):
    file: List[Dict]
    prompts: List[str]
    numImages: conint(gt=0)  
    password: constr(min_length=1)
