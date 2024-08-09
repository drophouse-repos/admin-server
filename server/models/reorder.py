from pydantic import BaseModel
from typing import List, Dict

class Reorder(BaseModel):
    file: List[Dict]
