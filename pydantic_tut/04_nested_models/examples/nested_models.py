from typing import List, Optional

from pydantic import BaseModel


class Address(BaseModel):
    street: str
    city: str
    pincode: str


class User(BaseModel):
    id: int
    name: str
    address: Address


class Comment(BaseModel):
    id: int
    content: str
    replies: Optional[List["Comment"]] = None


# TO do forward refferencing in pydatic we have to use below code
Comment.model_rebuild()


address1 = Address(street="123 something", city="test City", pincode="1234567890")

user = User(id=1, name="Aman Thakur", address=address1)

comment1 = Comment(
    id=1,
    content="wfghjwerty",
    replies=[Comment(id=2, content="Reply1"), Comment(id=3, content="Reply 2")],
)
