def binary_search(arr: list , target : int ) -> int: 
    """Iterative Approach"""
    
    left = 0
    right = len(arr) -1
    
    while left <= right:
        mid = (left + right) // 2
        
        if (arr[mid] == target):
            return mid

        elif target < arr[mid]:
            right = mid - 1
        
        else:
            left = mid + 1
    
    return -1


target_list = [12 , 45 ,67 ,89 ,104 , 380]
target_ele = 104

print(binary_search(target_list,target_ele))