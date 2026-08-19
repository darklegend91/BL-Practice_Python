def _rank_for(final_score : int) -> str:
    if final_score <= 299:
        return "Novice Explorer"
    elif final_score <= 599:
        return "Skilled Adventurer"
    elif final_score <= 999:
        return "Master Strategist"
    else:
        return "Algorithm Legend"


def game_result(game_state : dict[str , int]):

    leaderboard_score = game_state['leaderboard_score']
    treasure_bonus = game_state['treasure_bonus']
    battle_score = game_state['battle_score']
    exploration_bonus = game_state['exploration_bonus']

    final_score = (
        leaderboard_score
        + treasure_bonus
        + battle_score
        + exploration_bonus
    )

    rank = _rank_for(final_score)

    print("\n===== GAME RESULT =====")
    print(f"\nPlayer Score: {leaderboard_score}")
    print(f"Treasure Bonus: {treasure_bonus}")
    print(f"Battle Score: {battle_score}")
    print(f"Exploration Bonus: {exploration_bonus}")
    print(f"\nFinal Score: {final_score}")
    print(f"Rank: {rank}")

    if leaderboard_score == 0 and battle_score == 0 \
            and treasure_bonus == 0 and exploration_bonus == 0:
        print("\n(Tip: play missions 1, 2, 4 and 5 first to build up your score!)")
