'''
Email Marketing Duplicate Checker for Subscribers and New Sign-ups
=> A marketing manager has two email lists - one for current subscribers and another for new sign-ups.
=> Since the data is old, among the new sign-ups, there is a possibility that some of the new sign up members are already present in the current subscribers list.
=> Marketing manager wants a software solution to check whether any such email ids exist or not and if yes, share the email ids.
=> To help the marketing manager - plan developing a program.

TESTCASE 1:
Input =>
Enter the current subscribers' emails (comma-separated): alice@example.com, john@example.com, bob@example.com
Enter the new sign-ups' emails (comma-separated): john@example.com, mary@example.com, david@example.com

Output =>
The following email addresses are present in both lists: john@example.com

TESTCASE 2:
Input =>
Enter the current subscribers' emails (comma-separated): alice@example.com, john@example.com, bob@example.com
Enter the new sign-ups' emails (comma-separated): mary@example.com, david@example.com

Output =>
There are no common email addresses between current subscribers and new sign-ups.

Hint =>
=> Use the isdisjoint() method check if sets has a common elements
=> If above condition is true then use the intersection() method to display common elements
'''
# PROG 4: Email Marketing Duplicate Checker

current_input = input(
    "Enter the current subscribers' emails (comma-separated): "
)

new_input = input(
    "Enter the new sign-ups' emails (comma-separated): "
)

current_subscribers = {
    email.strip().lower()
    for email in current_input.split(",")
    if email.strip()
}

new_signups = {
    email.strip().lower()
    for email in new_input.split(",")
    if email.strip()
}

if current_subscribers.isdisjoint(new_signups):
    print(
        "There are no common email addresses between current "
        "subscribers and new sign-ups."
    )
else:
    common_emails = current_subscribers.intersection(new_signups)

    print("The following email addresses are present in both lists:")

    for email in sorted(common_emails):
        print(email)