from typing import Optional

from pydantic import BaseModel


class Cart (BaseModel):
    user_id : int
    items  : list[str]
    quantities : dict[str , int]


class BlogPost(BaseModel):
    title : str
    content  : str
    imageurl : Optional[str] = None
    