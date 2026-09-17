from typing import Optional

from pydantic import BaseModel, Field


class Employee(BaseModel):
    id: int
    name: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="This is employee name",
        examples=["Aman Thakur"]
    )
    department: Optional[str] = "General"
    salary: float = Field(
        ...,
        ge=10000
    )
    