import psycopg

from database import get_db_connection


def create_customer(customer):
    try:
        with get_db_connection() as conn , conn.cursor() as cursor:
                query = """
                    INSERT INTO customers (name, email, phone, city, age)
                    VALUES (%s, %s, %s, %s, %s) RETURNING customer_id;
                """
                cursor.execute(query, (customer.name, customer.email, customer.phone, customer.city, customer.age))
                conn.commit()
                return cursor.fetchone()["customer_id"] # type: ignore
    except psycopg.errors.UniqueViolation:
        return None  # Handles Duplicate Email gracefully

def get_customers():
    with get_db_connection() as conn , conn.cursor() as cursor:
            cursor.execute("SELECT * FROM customers ORDER BY customer_id ASC;")
            return cursor.fetchall()

def get_customer_by_id(customer_id: int):
    with get_db_connection() as conn , conn.cursor() as cursor:
            cursor.execute("SELECT * FROM customers WHERE customer_id = %s;", (customer_id,))
            return cursor.fetchone()

def update_customer(customer_id: int, customer):
    with get_db_connection() as conn , conn.cursor() as cursor:
            query = """
                UPDATE customers
                SET name = %s, email = %s, phone = %s, city = %s, age = %s
                WHERE customer_id = %s;
            """
            cursor.execute(query, (customer.name, customer.email, customer.phone, customer.city, customer.age, customer_id))
            conn.commit()
            return cursor.rowcount > 0

def delete_customer(customer_id: int):
    with get_db_connection() as conn , conn.cursor() as cursor:
            cursor.execute("DELETE FROM customers WHERE customer_id = %s;", (customer_id,))
            conn.commit()
            return cursor.rowcount > 0
        
        
# Pg Admin SQL Queries
# CREATE TABLE CUSTOMERS (
# 	CUSTOMER_ID SERIAL PRIMARY KEY,
# 	NAME VARCHAR(100) NOT NULL,
# 	EMAIL VARCHAR(150) UNIQUE NOT NULL,
# 	PHONE VARCHAR(15) NOT NULL,
# 	CITY VARCHAR(100) NOT NULL,
# 	AGE INTEGER CHECK (AGE >= 18),
# 	CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# )

# INSERT INTO
# 	CUSTOMERS (NAME, EMAIL, PHONE, CITY, AGE)
# VALUES
# 	(
# 		'Aarav Sharma',
# 		'aarav@example.com',
# 		'9876543210',
# 		'Delhi',
# 		28
# 	),
# 	(
# 		'Neha Gupta',
# 		'neha@example.com',
# 		'9876543211',
# 		'Mumbai',
# 		32
# 	),
# 	(
# 		'Rohan Desai',
# 		'rohan@example.com',
# 		'9876543212',
# 		'Pune',
# 		25
# 	),
# 	(
# 		'Priya Singh',
# 		'priya@example.com',
# 		'9876543213',
# 		'Delhi',
# 		22
# 	),
# 	(
# 		'Amit Patel',
# 		'amit@example.com',
# 		'9876543214',
# 		'Ahmedabad',
# 		40
# 	);

# Retrieve all customers
# select * from customers

# select * from customers where customer_id = 1

# select * from customers where city = 'Delhi'

# update customers
# set city = 'jaipur'
# where customer_id = 1

# update customers 
# set name = 'Neha Mehra'
# where customer_id = 2

# update customers 
# set phone = 9876543220
# where customer_id = 3
	
# delete from customers
# where customer_id = 5
