from pydantic import BaseModel, EmailStr, Field


class Customer(BaseModel):
    name : str
    phone: str
    city: str
    email : EmailStr
    age : int = Field(
        ...,
        ge = 18
    )