import datetime
from pydantic import StringConstraints, BaseModel, Field, conint  # , EmailStr, validator
from typing import Optional, Union
from typing_extensions import Annotated


class ItemModel(BaseModel):

    apparel: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="apparel", description="Apparel type is required."
    )
    size: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="size", description="Size is required."
    )
    color: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="color", description="Color is required."
    )
    img_id: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="img_id", description="Unique image ID is required."
    )
    prompt: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="prompt", description="Prompt is required."
    )
    timestamp: Optional[datetime.datetime] = Field(
        None, alias="timestamp", description="Timestamp is optional."
    )
    thumbnail: Optional[str] = Field(
        None, alias="thumbnail", description="thumbnail is only for cart Items."
    )
    toggled: Optional[Union[str, bool]] = Field(
        None, alias="toggled", description="Toggled is optional."
    )
    price: Annotated[int, conint(ge=1)] = Field(
        ..., alias="price", description="price is required."
    )