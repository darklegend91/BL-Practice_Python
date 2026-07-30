'''
Club Membership Renewal Manager
=> As a club manager, you have a list of persons who are members of the club.
=> You have also a list of members renewed their membership.
=> Some of the members who renewed had discontinued and might not be present in the list of members.
=> Plan creating a new list of members.

Input => \

Enter the names of current members (comma-separated): Alice,bob,charlie,david,eve

Enter the names of renewed members (comma-separated): alice,david, frank, grace

Output => \

Updated club members list:
Bob
Frank
Grace
Charlie
Eve
Hint =>
=> Use the symmetric_difference_update() method of a set to update set1 by adding items from set2, except common items.
=> Make the program case-insensitive
'''
# PROG 3: Club Membership Renewal Manager

current_input = input(
    "Enter the names of current members (comma-separated): "
)

renewed_input = input(
    "Enter the names of renewed members (comma-separated): "
)

# Convert each name to lowercase to make comparison case-insensitive
current_members = {
    name.strip().lower()
    for name in current_input.split(",")
    if name.strip()
}

renewed_members = {
    name.strip().lower()
    for name in renewed_input.split(",")
    if name.strip()
}

# Keep names present in only one of the two sets
current_members.symmetric_difference_update(renewed_members)

print("\nUpdated club members list:")

for member in sorted(current_members):
    print(member.title())