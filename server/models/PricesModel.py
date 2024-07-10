from pydantic import StringConstraints, BaseModel, Field
from typing_extensions import Annotated

class PricesModel(BaseModel):
	apparel: Annotated[str, StringConstraints(min_length=1)] = Field(
		..., alias="apparel", description="Apparel type is required."
	)
	price: int = Field(..., alias="price", description="Price type is required")