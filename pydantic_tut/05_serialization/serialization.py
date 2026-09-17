from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

# Address model
class Address(BaseModel):
    street: str
    city: str
    pincode: str

# User model
class User(BaseModel):
    id: int
    name: str
    email: str
    isactive: bool = True
    created_at: datetime
    address: Address
    tags: list[str] = Field(default_factory=list)  # Safe default

    # Model configuration for JSON encoding
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.strftime('%d-%m-%Y %H:%M:%S')  # Fixed typo
        }
    )

# Create a user instance
user = User(
    id=1,
    name="aman",
    email="a@gmail.com",
    created_at=datetime(2024, 3, 15, 14, 30),
    isactive=True,
    address=Address(
        street='romio',
        city='Japipur',
        pincode='17001'
    ),
    tags=['User', 'admin', 'customer']
)

# Convert to dict
python_dict = user.model_dump()
print("Python dict:", python_dict)

# Convert to JSON
python_json = user.model_dump_json()
print("JSON output:", python_json)
