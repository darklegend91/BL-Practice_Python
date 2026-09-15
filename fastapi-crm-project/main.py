import uvicorn
from fastapi import FastAPI, HTTPException

import crud
from schemas import Customer

app= FastAPI(title="Customer management Api")

@app.get('/')
def read_base_url():
    return ("This is a fastpi implemetation using psycopg  to use postgres from apis")

@app.get('/customers')
def get_all_customers():
    return crud.get_customers()

@app.get('/customers/{customer_id}')
def get_customer_by_id(customer_id: int):
    customer = crud.get_customer_by_id(customer_id)
    
    if not customer:
        raise HTTPException(status_code = 404 , detail = "customer not found!")
    
    return customer

@app.post('/customers' , status_code = 201)
def create_customer(customer: Customer):
    new_id = crud.create_customer(customer)
    
    if not new_id:
        raise HTTPException(status_code = 400 , detail = "Email already exsists!")
    
    return {"message": "customer created succesfully", "New customer id is " : new_id}

@app.put("/customers/{customer_id}")
def update_customer(customer_id: int , customer : Customer):
    updated = crud.update_customer(customer_id , customer)
    if not updated:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"message": "Customer updated successfully"}

@app.delete('/customer/{customer_id}')
def delete_customer_by_id(customer_id : int):
    deleted = crud.delete_customer(customer_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"message": "Customer deleted successfully"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
