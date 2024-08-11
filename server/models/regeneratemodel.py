from pydantic import BaseModel, conint, constr
from typing import List

class Regenerate(BaseModel):
    prompts: str
    password: constr(min_length=1)
