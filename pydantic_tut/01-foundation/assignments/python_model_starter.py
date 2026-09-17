from pydantic import BaseModel

# TODO : Creta e product Model with id , name , price , in_stock

class Product(BaseModel):
    id : int
    name : str
    price : float
    in_stock : bool