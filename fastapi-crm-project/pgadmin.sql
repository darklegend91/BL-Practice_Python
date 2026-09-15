CREATE TABLE CUSTOMERS (
	CUSTOMER_ID SERIAL PRIMARY KEY,
	NAME VARCHAR(100) NOT NULL,
	EMAIL VARCHAR(150) UNIQUE NOT NULL,
	PHONE VARCHAR(15) NOT NULL,
	CITY VARCHAR(100) NOT NULL,
	AGE INTEGER CHECK (AGE >= 18),
	CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

INSERT INTO
	CUSTOMERS (NAME, EMAIL, PHONE, CITY, AGE)
VALUES
	(
		'Aarav Sharma',
		'aarav@example.com',
		'9876543210',
		'Delhi',
		28
	),
	(
		'Neha Gupta',
		'neha@example.com',
		'9876543211',
		'Mumbai',
		32
	),
	(
		'Rohan Desai',
		'rohan@example.com',
		'9876543212',
		'Pune',
		25
	),
	(
		'Priya Singh',
		'priya@example.com',
		'9876543213',
		'Delhi',
		22
	),
	(
		'Amit Patel',
		'amit@example.com',
		'9876543214',
		'Ahmedabad',
		40
	);

Retrieve all customers
select * from customers

select * from customers where customer_id = 1

select * from customers where city = 'Delhi'

update customers
set city = 'jaipur'
where customer_id = 1

update customers 
set name = 'Neha Mehra'
where customer_id = 2

update customers 
set phone = 9876543220
where customer_id = 3
	
delete from customers
where customer_id = 5
