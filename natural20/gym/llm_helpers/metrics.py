from typing import Dict, Any


def combat_metrics(env) -> Dict[str, Any]:
    """Compute basic metrics for a finished dndenv combat.

    Args:
        env: The :class:`dndenv` instance after the battle concludes.

    Returns:
        Dictionary containing:
            - ``win`` (bool): ``True`` if the groups controlled by the LLMs
              are part of the winning groups.
            - ``turns_taken`` (int): Total number of turns played.
            - ``survivors`` (dict): Mapping of surviving agent names to a tuple
              ``(hp, max_hp)`` at the end of combat.
    """
    battle = getattr(env, "battle", None)
    if battle is None:
        raise ValueError("env does not contain a battle")

    players = getattr(env, "players", None)
    # players is a list of tuples (group_name, group_type, player_name, player_position) where group_type is either "H" (heroes) or "E" (enemies)
    heroes_groups = {group for group, group_type, _, _ in players if group_type == "H"}
    if not heroes_groups:
        raise ValueError("No hero groups found in the battle")

    winning_groups = battle.winning_groups()
    win = any(group in winning_groups for group in heroes_groups)

    survivors = {}
    for group, _, player, _ in env.players:
        if group in env.control_groups and not player.dead():
            survivors[player.name] = (player.hp(), player.max_hp())

    return {
        "win": win,
        "turns_taken": env.time_step,
        "survivors": survivors,
    }


def combat_score(
    metrics: Dict[str, Any], weights: Dict[str, float] | None = None
) -> float:
    """Generate a score for a combat run based on the metrics.

    The score is a weighted sum of several components. By default the
    components are weighted as follows:

    ``win`` (100 points if ``True``), ``survivor_hp`` (sum of
    surviving HP ratios times 10), and ``turns_taken`` (1 point
    deducted per turn).  Consequently, finishing a battle in fewer
    turns yields a higher score.

    Args:
        metrics: Dictionary returned by :func:`combat_metrics`.
        weights: Optional mapping overriding the default weight values.

    Returns:
        A numeric score useful for comparing different runs.
    """

    if weights is None:
        weights = {"win": 100.0, "survivor_hp": 10.0, "turns_taken": 1.0}

    win_score = weights.get("win", 0.0) if metrics.get("win") else 0.0

    survivor_hp_ratio = 0.0
    for hp, max_hp in metrics.get("survivors", {}).values():
        if max_hp > 0:
            survivor_hp_ratio += hp / max_hp

    survivor_score = survivor_hp_ratio * weights.get("survivor_hp", 0.0)

    turn_penalty = metrics.get("turns_taken", 0) * weights.get("turns_taken", 0.0)

    return win_score + survivor_score - turn_penalty
