from pydantic import BaseModel, Field, constr
from typing import List, Dict, Optional, Union


class Dimensions(BaseModel):
    top: float
    left: float
    height: float
    width: float

class Asset(BaseModel):
    front: str
    back: str
class Color(BaseModel):
    name: str = Field(..., description="Color name is required.")
    asset: Asset = Field(default_factory=list, description="product asset.")
    color_map: str

class Product(BaseModel):
    name: constr(min_length=1) = Field(..., description="Product name is required.")
    description: Optional[constr(min_length=1)] = Field(None, description="Product description.")
    default_color: Optional[constr(min_length=1)] = Field(None, description="Product default color.")
    sizes: List[str] = Field(default_factory=list, description="Product sizes.")
    mask: Optional[str] = Field(None, description="Product mask as Base64 encoded image.")
    # colors: Dict[str, Optional[constr(min_length=1)]] = Field(default_factory=dict, description="Product colors.")
    # clip: Optional[str] = Field(b"data:image/png;base64", description="product Clip image as Base64 encoded image.")
    colors: Dict[str, Optional[Color]] = Field(default_factory=dict, description="Product colors.")
    defaultProduct: Optional[str] = Field(b"data:image/png;base64", description="Default product image as Base64 encoded image.")
    dimensions: Dimensions = Field(..., description="Product dimensions.")

class LandingPage(BaseModel):
    name: constr(min_length=1) = Field(..., description="Product name is required.")
    asset: str = Field(..., description="Front asset is required.")
    asset_back: str

class OrganizationModel(BaseModel):
    org_id: constr(min_length=1) = Field(..., description="Organization ID is required.")
    name: Optional[constr(min_length=1)] = Field(None, description="Organization name.")
    mask: Optional[str] = Field(None, description="Organization mask as Base64 encoded image.")
    logo: Optional[str] = Field(None, description="Organization logo as Base64 encoded image.")
    green_mask: Optional[str] = Field(None, description="Organization Green Mask as Base64 encoded image.")
    theme_color: Optional[constr(min_length=1)] = Field("#FF007F", description="Organization theme color.")
    font: Optional[constr(min_length=1)] = Field(None, description="Organization font.")
    favicon: Optional[str] = Field(None, description="Organization favicon.")
    landingpage: List[LandingPage] = Field(..., description="List of Sample Products.")
    products: List[Product] = Field(..., description="List of products.")