from pydantic import BaseModel

class UserData(BaseModel):
    id: int
    name : str
    is_active : bool
    
    
input_data = {'id':  101 , 'name': "Chai" , 'is_active' : 'True'}

user = UserData(**input_data)
print(user)