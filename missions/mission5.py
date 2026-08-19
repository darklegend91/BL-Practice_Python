
def battle(monsters : dict[str , dict[str , int]]):

    print("\nAvailable Monsters:")
    for name in monsters:
        stats = monsters[name]
        print(f"  {name}  (Health: {stats['health']}, Attack: {stats['attack']}, Reward: {stats['reward']})")

    choice = input("\nChoose a monster to battle: ").strip()

    if choice not in monsters:
        print("No such monster in the kingdom!")
        return

    stats = monsters[choice]

    battle_score = stats['reward'] + (stats['health'] // 10) - stats['attack']

    print(f"""
        Monster: {choice}
        Battle Score: {battle_score}""")

    return battle_score
