import argparse
import sys
import pickle as pkl
from gymnasium import make
from samples.llm_interface import SoloGPT4Interfacer, MultiGPT4Interfacer
import os
import random
from natural20.gym.llm_helpers.metrics import combat_metrics, combat_score
from experiment_object import Experiment

sys.path.append(os.getcwd())
os.environ["OPENAI_API_KEY"] = ""

parser = argparse.ArgumentParser()
parser.add_argument("--exp_id", type=int, default=0)
parser.add_argument("--communication", type=int, default=0)

args = parser.parse_args()

exp_id = args.exp_id
do_communication = (args.communication > 0)

layout_path = "results/"
if not os.path.exists(layout_path):
    os.mkdir(layout_path)
result_path = layout_path + ("multi/" if do_communication else "solo/")

if not os.path.exists(result_path):
    os.mkdir(result_path)

result_path += f"experiment_{exp_id}.pkl"
if os.path.exists(result_path):
    print(f"\n\n XXXXXXX Experiment number {exp_id} skipped, already done XXXXXXX")

else :
    layout_path += "layouts/"
    if not os.path.exists(layout_path):
        os.mkdir(layout_path)

    layout_path += f"experiment_{exp_id}.pkl"
    if os.path.exists(layout_path):
        with open(layout_path, "rb") as f:
            poses, combat_order, a_player, e_player = pkl.load(f)
        env = make(
            "dndenv-v0",
            render_mode="ansi",
            map_file="maps/game_map.yml",
            show_logs=False,
            profiles=a_player,
            enemies=e_player,
            control_groups=["a","b"]
            )
        f = lambda m, p : 18 - (10 * combat_order.index(p.name))
        observation, info = env.reset(seed = random.randint(0,1000), options={"initial_poses":poses, "initiative":f})


    else:
        n_player1 = 2
        n_player2 = 2
        # Initialize the environment
        # env = make("dndenv-v0", root_path="templates", render_mode="ansi")
        all_classes = ['halfling_rogue.yml', 'high_elf_fighter.yml']
        all_players = ["Alysha", "Bernard", "Cedric", "Didier", "Eric", "Francois", "Gertrude", "Heloise", "Isabelle"]
        players = random.sample(all_players, n_player1 + n_player2)
        a_player = [(random.choice(all_classes), player) for player in players[:n_player1]]
        e_player = [(random.choice(all_classes), player) for player in players[n_player1:]]

        env = make(
            "dndenv-v0",
            render_mode="ansi",
            map_file="maps/game_map.yml",
            show_logs=False,
            profiles=a_player,
            enemies=e_player,
            control_groups=["a","b"]
            )

        observation, info = env.reset(seed = random.randint(0,1000))

        poses = [[], []]
        for (gr, _, name, pos) in env.env.env.players:
            poses[gr=="b"].append(pos)
        
        combat_order = [entity.name for entity in env.env.env.battle.combat_order]

        with open(layout_path, "wb") as f:
            pkl.dump([poses, combat_order, a_player, e_player], f)

    envi = env.env.env
    conversational_groups = {"a":do_communication, "b":False}

    agents = {}
    groups = env.env.env.battle.groups  
    for character in env.env.env.battle.combat_order:
        gr = None
        for group_name, group in env.env.env.battle.groups.items():
            if character in group:
                gr = group_name
        if gr == None : print(f"Warning ! : Character {character.name} has no friends !!! (aka no groups attributed)")
        agent_type = MultiGPT4Interfacer if conversational_groups[gr] else SoloGPT4Interfacer
        agents[character.name] = (agent_type(debug=False, explain=True, name=character.name), gr, character)


    expe = Experiment(env, env.env.env, agents, conversational_groups=conversational_groups, debug=False)

    while not expe.finished:
        expe.run_till_end(max_step=199)
    
    metrics = combat_metrics(expe.dnd_environment, agents)
    score = combat_score(metrics)
    res = {"a":a_player, "b":e_player, "conversations":expe.conversations, "metrics":metrics, "score": score, "backlog":expe.backlog}

    with open(result_path, "wb") as f:
        pkl.dump(res, f)
    
    print(f"OOOOOOOOO Experiment number {exp_id} runned with sucess OOOOOOOOO")

