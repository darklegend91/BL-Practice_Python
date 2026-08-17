import csv

with open('data.csv') as file:
    with open('data2.csv' , 'w') as new_file:
        csv_writer = csv.writer( new_file , delimiter= ';')
        csv_reader = csv.reader(file)
        for row in csv_reader:
            print(row)
            csv_writer.writerow(row)