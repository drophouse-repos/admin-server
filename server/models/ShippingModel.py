from pydantic import (
    field_validator,
    StringConstraints,
    ConfigDict,
    BaseModel,
    Field,
    EmailStr,
)
from typing import Optional
from typing_extensions import Annotated
from enum import Enum


class AddressType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class ShippingModel(BaseModel):
    firstName: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="firstName", description="First name is required."
    )
    lastName: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="lastName", description="Last name is required."
    )
    email: EmailStr = Field(..., alias="email")
    phone: Annotated[str, StringConstraints(min_length=10, max_length=15)] = Field(
        ..., alias="phone", description="Phone number must be between 10 and 15 digits."
    )
    streetAddress: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="streetAddress", description="Street address is required."
    )
    streetAddress2: Optional[str] = Field(
        None, alias="streetAddress2", description="Secondary street address (optional)."
    )
    city: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="city", description="City is required."
    )
    stateProvince: Annotated[str, StringConstraints(min_length=1)] = Field(
        ..., alias="stateProvince", description="State/Province is required."
    )
    postalZipcode: Annotated[str, StringConstraints(min_length=5, max_length=10)] = (
        Field(
            ...,
            alias="postalZipcode",
            description="Postal/Zip code must be between 5 and 10 characters.",
        )
    )
    addressType: AddressType = Field(
        ..., description="Address type should be either primary or secondary."
    )
    model_config = ConfigDict(populate_by_name=True)

    @field_validator("email")
    @classmethod
    def email_must_contain_at_symbol(cls, value):
        if "@" not in value:
            raise ValueError("Email must contain an @ symbol")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_be_numeric(cls, value):
        if not value.isdigit():
            raise ValueError("Phone number must contain only digits")
        return value

    @field_validator("postalZipcode")
    @classmethod
    def postal_code_validation(cls, value):
        if not value.isalnum():
            raise ValueError("Postal/Zip code must be alphanumeric")
        return value
