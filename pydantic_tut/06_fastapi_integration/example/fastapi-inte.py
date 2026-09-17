from fastapi import FastAPI , Depends
from pydantic import BaseModel , EmailStr

app = FastAPI()

class UserSignup(BaseModel):
    username : str
    email : EmailStr
    password : str
    
    
class Settings(BaseModel):
    app : str = "Test App"
    admin_email : EmailStr = 'admin@gmail.com'


def get_seetings():
    return Settings()

@app.get('/')
def base_url():
    return {'This is app made using fastapi integarting pydantic for data validation'}

@app.post('/signup')
def signup(user_data : UserSignup):
    return {"Message" : f'user {user_data.username} signup Succesfully'}

@app.get('/settings')
def get_settings(settings :Settings = Depends(get_seetings)):
    return settings