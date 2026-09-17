from fastapi import FastAPI
from pydantic.pydantic import BaseModel

app = FastAPI()

class Tea(BaseModel):
    id : int
    name : str
    origin: str
    
teas: list[Tea] = []

@app.get("/")
def read_root():
    return {"Message": "Welecome to the fast api app"}

@app.get("/teas")
def get_teas():
    return teas

@app.post("/teas")
def add_tea(tea: Tea):
    teas.append(tea)
    return tea

@app.put("/teas/{tea_id}")
def update_tea(tea_id: int , updated_tea: Tea):
    for index , tea in enumerate(teas):
        if tea.id == tea_id:
            teas[index] = updated_tea
            return updated_tea
    return {"error": " Tea not found to be update"}

@app.delete("/teas/{tea_id}")
def delete_tea(tea_id):
    for index , tea in enumerate(teas):
        if tea.id == tea_id :
            deleted_tea = teas.pop(index)
            return deleted_tea
        
    return {"error": "Tea not found"}