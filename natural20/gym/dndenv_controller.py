from natural20.actions.look_action import LookAction
from natural20.actions.stand_action import StandAction
from natural20.actions.attack_action import AttackAction
from natural20.actions.move_action import MoveAction
from natural20.gym.types import EnvObject, Environment
from natural20.entity import Entity
from natural20.action import Action
from natural20.controller import Controller
from natural20.gym.tools import dndenv_action_to_nat20action, build_observation, \
    build_info, action_to_gym_action
import math
import copy
import os

class DndenvController(Controller):

    VALID_ACTIONS = ["attack",
                     "two_weapon_attack",
                     "move",
                     "disengage",
                     "disengage_bonus",
                     "dodge",
                     "dash",
                     "dash_bonus",
                     "second_wind",
                     "action_surge",
                     "prone",
                     "spell",
                     "shove"]

    """
    Wrapper for Gym Agents to interact with Natural20
    """
    def __init__(self, session, agent: object, entity_embeddings: str = 'entity_token_map.csv', weapon_embeddings: str = 'weapon_token_map.csv',
                 spell_embeddings: str = 'spell_token_map.csv'):
        self.state = {}
        self.session = session
        self.battle_data = {}
        self.agent = agent

        def read_mappings(file_path, mappings):
            with open(file_path, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    mappings[parts[0]] = int(parts[1])

        fname = os.path.join(self.session.root_path, entity_embeddings)
        self.entity_mappings = {}
        read_mappings(fname, self.entity_mappings)

        fname = os.path.join(self.session.root_path, weapon_embeddings)
        self.weapon_mappings = {}
        read_mappings(fname, self.weapon_mappings)

        fname = os.path.join(self.session.root_path, spell_embeddings)
        self.spell_mappings = {}
        read_mappings(fname, self.spell_mappings)

    # @param entity [Natural20::Entity]
    def register_handlers_on(self, entity):
        entity.attach_handler("opportunity_attack", self.opportunity_attack_listener)

    def begin_turn(self, entity):
        print(f"{entity.name} begins turn")

    def roll_for(self, entity, stat, advantage=False, disadvantage=False):
        return None
    
    def opportunity_attack_listener(self, battle, session, entity, map, event):
        actions = [s for s in entity.available_actions(session, battle, opportunity_attack=True)]

        valid_actions = []
        for action in actions:
            valid_targets = battle.valid_targets_for(entity, action)
            if event['target'] in valid_targets:
                action.target = event['target']
                action.as_reaction = True
                valid_actions.append(action)

        selected_action = self.select_action(battle, entity, valid_actions, reaction=event)
        return selected_action

    def select_action(self, battle, entity, available_actions = None, reaction=None) -> Action:
        if available_actions is None:
            available_actions = []
        entity_map = battle.map_for(entity)
        observation = build_observation(battle, entity_map, entity, self.entity_mappings, self.weapon_mappings)
        available_moves = action_to_gym_action(entity, entity_map, available_actions, weapon_mappings=self.weapon_mappings, \
                                                   spell_mappings=self.spell_mappings)
        info = build_info(battle, available_moves, entity, self.weapon_mappings, self.spell_mappings, self.entity_mappings)

        if reaction:
            info['trigger'] = reaction['trigger']
            info['entity'] = self.entity_mappings[entity.class_descriptor()]
            info['reactor'] = entity.name

        gym_action = self.agent.action(observation, info)

        if gym_action[0] == -1:
            return None

        action = dndenv_action_to_nat20action(entity, battle, entity_map, \
                                             available_actions, \
                                             gym_action, \
                                             weapon_mappings=self.weapon_mappings, \
                                             spell_mappings=self.spell_mappings)

        return action

    def move_for(self, entity: Entity, battle):
        # choose available moves at random and return it
        available_actions = self._compute_available_moves(entity, battle)
        # environment, entity = self._build_environment(battle, entity)
        return self.select_action(battle, entity, available_actions)

    def select_reaction(self, entity, battle, map, valid_actions, event):
        if len(valid_actions) == 0:
            return None

        action = self.select_action(battle, entity, valid_actions, reaction=event)
        return action

    # Build a suitable environment for Reinforcement Learning
    def _build_environment(self, battle, entity):
        enemy_positions = {}
        self._observe_enemies(battle, entity, enemy_positions)
        objects = []

        for enemy, location in enemy_positions.items():
            equipped_items = []
            for item in enemy.equipped_items():
                equipped_items.append(item['name'])
            is_enemy = enemy in battle.opponents_of(entity)
            env_object = EnvObject(enemy.name, 'pc', enemy.hp()/enemy.max_hp(), location, equipped_items, is_enemy=is_enemy)
            objects.append(env_object)
        environment = Environment(battle.map, objects, {
            "available_movement" : entity.available_movement(battle),
            "available_actions" : entity.total_actions(battle),
            "available_reactions" : entity.total_reactions(battle),
            "available_bonus_actions" : entity.total_bonus_actions(battle)
        })
        return environment, entity

    # gain information about enemies in a fair and realistic way (e.g. using line of sight)
    # @param battle [Natural20::Battle]
    # @param entity [Natural20::Entity]
    def _observe_enemies(self, battle, entity, enemy_positions=None):
        if enemy_positions is None:
            enemy_positions = {}

        objects_around_me = battle.map_for(entity).look(entity)

        my_group = battle.entity_group_for(entity)

        for object, location in objects_around_me.items():
            group = battle.entity_group_for(object)
            if group == "none":
                continue
            if not group:
                continue
            if not object.conscious():
                continue

            if group != my_group:
                enemy_positions[object] = location 

    def _initialize_battle_data(self, battle, entity):
        if battle not in self.battle_data:
            self.battle_data[battle] = {}
        if entity not in self.battle_data[battle]:
            self.battle_data[battle][entity] = {
                'known_enemy_positions': {},
                'hiding_spots': {},
                'investigate_location': {}
            }

    def _compute_available_moves(self, entity, battle):
        self._initialize_battle_data(battle, entity)

        # known_enemy_positions = self.battle_data[battle][entity]['known_enemy_positions']
        # hiding_spots = self.battle_data[battle][entity]['hiding_spots']
        investigate_location = self.battle_data[battle][entity]['investigate_location']

        enemy_positions = {}
        self._observe_enemies(battle, entity, enemy_positions)
        available_actions = entity.available_actions(self.session, battle)

        # generate available targets
        valid_actions = []
        # check if enemy positions is empty

        if len(enemy_positions.keys()) == 0 and len(investigate_location) == 0 and LookAction.can(entity, battle):
            action = LookAction(self.session, entity, "look")
            valid_actions.append(action)

        # try to stand if prone
        if entity.prone() and StandAction.can(entity, battle):
            valid_actions.append(StandAction(None, entity, "stand"))

        for action in available_actions:
            if action.action_type in self.VALID_ACTIONS:
                valid_actions.append(action)

        return valid_actions

    def _get_enemy_positions(self, battle, entity):
        enemy_positions = {}
        self._observe_enemies(battle, entity, enemy_positions)
        return enemy_positions
    
    # Sort actions based on success rate and damage
    def _sort_actions(self, battle, available_actions):
        sorted_actions = []
        for action in available_actions:
            if isinstance(action, AttackAction):
                base_score = action.compute_hit_probability(battle) * action.avg_damage(battle)
                sorted_actions.append((action, base_score))
            elif isinstance(action, MoveAction):
                # get known enemy position
                enemy_positions = self._get_enemy_positions(battle, action.source)
                # get the closest enemy
                closest_enemy = None
                min_distance = math.inf
                for enemy, location in enemy_positions.items():
                    distance = battle.map.distance(action.source, enemy, location)
                    if distance < min_distance:
                        min_distance = distance
                        closest_enemy = enemy
                if closest_enemy:
                    # get the distance to the closest enemy
                    new_position = action.move_path[-1]
                    # print(f"closest_enemy {closest_enemy.name} {enemy_positions[closest_enemy]}")
                    distance = battle.map.distance(action.source, closest_enemy)
                    new_distance = battle.map.distance(action.source, closest_enemy, entity_1_pos=new_position)

                    # select movement which brings closer to the enemy
                    score = distance - new_distance
                    # print(f"scores {distance} {new_distance} {score}")
                    sorted_actions.append((action, score))
                else:
                    sorted_actions.append((action, 0))
            else:
                sorted_actions.append((action, 0))
        sorted_actions.sort(key=lambda a: a[1], reverse=True)
        sorted_actions = [a[0] for a in sorted_actions]
        return sorted_actions