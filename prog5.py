'''
PROG 5: Transpose Matrix

Transpose a matrix: Given a 3 X 3 matrix of numbers as two dimensional list of numbers, develop a function which does transpose this matrix
Input => \
Original Matrix :\
[1, 2, 3]\
[4, 5, 6]\
[7, 8, 9]
Output =>
```
Transpose matrix
[1, 4, 7]
[2, 5, 8]
[3, 6, 9]

```
'''

def transpose_matrix(matrix):
    if not matrix or not matrix[0]:
        raise ValueError("Matrix must not be empty.")

    number_of_columns = len(matrix[0])

    for row in matrix:
        if len(row) != number_of_columns:
            raise ValueError(
                "All matrix rows must have the same length."
            )

    transposed_matrix = []

    for column_index in range(number_of_columns):
        new_row = []

        for row_index in range(len(matrix)):
            new_row.append(
                matrix[row_index][column_index]
            )

        transposed_matrix.append(new_row)

    return transposed_matrix


original_matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9]
]

result = transpose_matrix(original_matrix)

print("Original matrix")

for row in original_matrix:
    print(row)

print("\nTranspose matrix")

for row in result:
    print(row)