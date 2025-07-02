
import random
from openai import OpenAI
import time
import os
import requests
import json
from natural20.gym.llm_helpers.prompting_utils import actions_to_prompt
import pdb
import re

class LLMInterfacer:
    def __init__(self, debug=False, explain=False):
        self.debug = debug
        self.explain = explain

    def select_action_for_state(self, state, info):
        # just return a random action for now
        # trunk-ignore(bandit/B311)
        action = random.choice(info['available_moves']) # assign random action instead
        return action
    
    def action(self, observation, info):
        return self.select_action_for_state(observation, info)

    def dndenv_state_to_prompt(self, state, info, players=None):
        player_positions = {}
        for el in players:
            player_positions[(el[3][0], el[3][1])] = el[2].name
        map = state["map"]
        actions, bonus_actions, reactions = state["turn_info"]
        player_type = state["player_type"][0]
        entity_mappings = info["entity_mappings"]
        # swap values to keys for entity mappings
        entity_mappings = {v: k for k, v in entity_mappings.items()}
        player_type_str = entity_mappings.get(player_type, "")
        player_type_str, player_level = player_type_str.split("-")
        health_pct = state["health_pct"]
        movement = state["movement"]
        conditions = state["conditions"]
        is_prone, is_dodging, is_grappled, is_disengaging, _, _, _, _ = conditions

        instruction_prompt = "We are playing a game of Dungeons and Dragons 5th Edition. It is current your turn and you play \n" + \
                             f"as a hero character denoted by {self.name[0]} (a level {player_level} {player_type_str})."
        instruction_prompt += f"Your health is at {health_pct*100}% specifically {info['health']}/{info['max_health']} \n"
        instruction_prompt += "Your current conditions are:\n"
        if is_prone:
            instruction_prompt += "Currently Prone\n"

        if is_dodging:
            instruction_prompt += "Currently Dodging\n"

        if is_disengaging:
            instruction_prompt += "Currently Disengaging\n"
        
        
        
        enemy_types = state["enemy_type"]
        health_enemy = state["health_enemy"]
        instruction_prompt += f"\nYou have as enemies :"
        for i, name in enumerate(state["enemy_name"]):
            is_enemy_prone, is_enemy_dodging, is_enemy_grappled, is_enemy_disengaging, _, _, _, _  = state["enemy_conditions"][i]
            enemy_type_str = entity_mappings.get(enemy_types[i], "")
            enemy_type_str, enemy_level = enemy_type_str.split("-")
            instruction_prompt += f"\n - {name} denoted by {name[0]} (a level {enemy_level} {enemy_type_str}).\n    Their health is currently at {health_enemy[i]*100}%."
            instruction_prompt += "\n    Their current conditions are: "
            if is_enemy_prone:
                instruction_prompt += "Currently Prone, "

            if is_enemy_dodging:
                instruction_prompt += "Currently Dodging, "

            if is_enemy_disengaging:
                instruction_prompt += "Currently Disengaging"
        instruction_prompt += "\nYou must defeat all of them in order to win.\n\n"


        ally_types = state["ally_type"]
        health_ally = state["health_ally"]
        if len(ally_types) > 0:
            instruction_prompt += f"You are helped in that regard by your allies :"
            for i, name in enumerate(state["ally_name"]):
                is_ally_prone, is_ally_dodging, is_ally_grappled, is_ally_disengaging, _, _, _, _  = state["ally_conditions"][i]
                ally_type_str = entity_mappings.get(ally_types[i], "")
                ally_type_str, ally_level = ally_type_str.split("-")
                instruction_prompt += f"\n - {name} denoted by {name[0]} (a level {ally_level} {ally_type_str}).\n    Their health is currently at {health_ally[i]*100}%."
                instruction_prompt += "\n    Their current conditions are: "
                if is_ally_prone:
                    instruction_prompt += "Currently Prone, "

                if is_ally_dodging:
                    instruction_prompt += "Currently Dodging, "

                if is_ally_disengaging:
                    instruction_prompt += "Currently Disengaging"

        instruction_prompt += "You have the following available actions and movement available:\n\n"
        instruction_prompt += f"Available movement: {movement}ft\n"
        instruction_prompt += f"Available actions: {actions}\n"
        instruction_prompt += f"Bonus actions: {bonus_actions}\n"
        instruction_prompt += f"Reactions: {reactions}\n\n"
        spell_slots = state["spell_slots"]
        for level, slots in enumerate(spell_slots):
            if slots > 0:
                instruction_prompt += f"Spell Slot Level {level + 1}: {slots} slots\n"
        prompt = instruction_prompt
        prompt += self.map_to_prompt(map, player_positions)
        if info.get('trigger', False):
            prompt += f"Note that this is not really your turn but a Reaction for {info['trigger']}:"
        prompt += actions_to_prompt(info['available_moves'], info["weapon_mappings"], info["spell_mappings"])
        prompt += "\n\nPlease choose the number corresponding to the action you would like to take.\n"
        prompt += "Provide your answer using the format, starting with the desired number choice, followed by the colon and the action.\n"
        if self.explain:
            prompt += "Following that line, please provide an explanation of why you chose that action.\n"

        prompt + "See sample below:\n\n"
        prompt += "<choice no.>: <choice description>\n"

        if self.explain:
            prompt += "explanation: I attacked the enemy because he was low and health.\n"
        else:
            prompt += "Just provide the action choice, no need to explain.\n"

        return prompt

    def map_to_prompt(self, map, player_positions):
        prompt =  "\n\nHere is a rough sketch of the map that considers line of sight to the enemy.\n"

        prompt += "Here is the map:\n"
        field_view = len(map)//2

        for i, row in enumerate(map):
            row_str = ""
            for j, col in enumerate(row):
                token = None

                entity_type, terrain, entity_int, health_pct, status = col

                if terrain == 255:
                    token = " "
                elif terrain == 1:
                    token = "."
                elif terrain == 2:
                    token = "*"
                elif terrain == 3:
                    token = "~"
                elif terrain == 4:
                    token = "o"
                elif terrain == 0:
                    token = "_"
                else:
                    raise ValueError(f"Invalid terrain value {terrain}")

                if entity_int == 1:
                    token = "P"
                elif entity_int == 2:
                    token = "E"
                elif entity_int == 3:
                    token = "A"
                elif entity_int == 4:
                    token = "?"
                
                if (i-field_view,j-field_view) in player_positions:
                    token = player_positions[(i-field_view,j-field_view)][0]

                row_str += token
            prompt += row_str + "\n"
        prompt +"\nHere is the legend for the map, note that each tile is 5ft by 5ft:\n"
        prompt += "areas with no characters are represented by a dot (.)\n"
        for name in player_positions.values():
            prompt += f"{name} is represented by {name[0]}\n"
        prompt += "Neutral characters are represented by a question mark (?)\n"
        prompt += "areas outside of the map are represented by a hash (_), you cannot move to areas with _\n"
        prompt += "areas with obstacles are represented by an asterisk (*)\n"
        prompt += "areas with a barrel are represented by an (o). These provide half-cover if right behind it and attacks are comming from the other side.\n"
        prompt += "areas with water are represented by a tilde (~) and are difficult terrain\n"
        prompt += "areas that the player can't see are just blanks/space\n"
        prompt += "Each tile of the map is 5ft by 5ft.\n\n"
        return prompt

class OllamaInterfacer(LLMInterfacer):
    def __init__(self, base_url="http://127.0.0.1:11434", model="deepseek-r1:7b", debug=False, explain=False):
        super().__init__(debug, explain=explain)
        self.base_url = base_url
        self.model = model
        self.explain = explain

    def select_action_for_state(self, state, info):
        prompt = self.dndenv_state_to_prompt(state, info)

        if self.debug:
            print(f"prompt: -------------------------------\n{prompt}\n---------------------------------")

        response = requests.post(self.base_url + '/api/generate', json={"prompt": prompt, "model": self.model, "stream": False})


        result = response.json()
        raw_text = result.get("response", "")
        # remove text in between <think>....</think>  and the tag themselves
        if self.explain:
            print(f"raw_text: {raw_text}")
        raw_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
        # remove newlines
        raw_text = raw_text.replace("\n", "")
        extracted = "".join(ch for ch in raw_text if ch.isdigit())
        choice = int(extracted[0]) if extracted else 0

        return info["available_moves"][choice - 1] if choice > 0 else random.choice(info["available_moves"])










class OGPT4Interfacer(LLMInterfacer):
    def __init__(self, variant="gpt-4.1", debug=False, api_key=None, base_url=None, tools=False, explain=False, weapon_mappings=None, max_retries=4, name="Bob"):
        """
        Args:
            api_key: the openai api key to use
            variant: the variant of the model to use, e.g. gpt-4o, gpt-4, etc.
            debug: whether to print debug information
        """
        super().__init__(debug, explain=explain)

        if api_key is None and base_url is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key is None:
                raise ValueError("Please set the OPENAI_API_KEY environment variable")

        self.variant = variant
        self.debug = debug
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries
        )
        self.name = name
        self.memory = []
        self.summary = "This is the first turn of the combat, nothing has happened yet."
        self.ongoing_conversation = None
        if tools:
            self.tools = [
                {
                    "type": "function",
                    "function": {
                    "name": "get_action",
                    "description": "get action for agent to execute",
                    "parameters": {
                        "type": "object",
                        "properties": {
                        "action": {
                            "type": "integer",
                            "description": "action to take",
                        }
                        },
                        "required": ["action"],
                    },
                    }
                }
            ]
        else:
            self.tools = None
        self.dev_prompt = self.make_dev_prompt()

        self.functions = [
            {
                "name": "read_action",
                "description": "Reads the action the character wants to perform in order to communicate it to the simulation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_id": {
                            "type": "integer",
                            "description": "Identifier of the chosen action as indicated in the last message"
                        },
                        "description": {
                            "type": "string",
                            "description": "Decription of the chosen action as indicated in the last message"
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Explanation of why you decided to make this action"
                        },
                        "content": {
                            "type": "string",
                            "description": "In case the chosen action is to communicate, the content of the message that should be sent to your allies."
                        }
                    }
                }
            },
            {
                "name": "rewrite_summary",
                "description": "Reads the rewritten summary in order to save it in the memory of the agent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "A summary of the situation the agent is in to be used as internal memory of said agent"
                        }
                    }
                }
            }
        ]
    

    def make_dev_prompt(self):
        prompt = ""
        prompt += f"We are playing a game of Dungeons and Dragons 5th Edition. You play and are referred to as {self.name}.\n"
        # prompt += f"The user will be giving you details on the current situation that your character is in along with a short summary of what happened previously. He will then ask you whether you want to take actions or not.\n"
        # prompt += f"You will communicate your will by using a properly formatted JSON schema given to you. Do not generate output that isn’t in properly formatted JSON.\n"
        # prompt += "\n\n\n"
        # prompt += "Here is an example of the format you should use for your answers :\n\n"
        # prompt += """
        # {
        #     "action": number corresponding to the desired action,
        #     "description": string that explains the action,
        #     "content": in case the chosen action is a communication, string containing the message to send to your allies,
        # }
        # """
        # prompt += "\n\nHere is an example of how to use it :\n"
        # prompt += """
        # {
        #     "action": <choice no.>,
        #     "description": <choice description>,
        #     "content": "I should have enough damage on my turn to deal with the gobelin, you can consider him dealt with and focus on the troll.
        # }
        # """
        return prompt


    def select_action_for_state(self, state, info, players, is_conversation = False):
        state_prompt = self.dndenv_state_to_prompt(state, info, players=players)
        if is_conversation:
            assert(self.ongoing_conversation != None)
            prompt = state_prompt + self.communication_prompting()
        else:
            prompt = state_prompt + self.action_prompting()
        
        # measure gpt-4o response time
        start_time = time.time()

        if self.debug:
            print(f"prompt: -------------------------------\n{prompt}\n---------------------------------")
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": self.dev_prompt
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=self.variant,
            functions = self.functions,
            function_call = {
                "name": "read_action"
            }
        )
        # if self.tools:
        #     orig_response = chat_completion.choices[0].message.tool_calls[0].function.arguments
            
        # else:
        #     orig_response = chat_completion.choices[0].message.content
        #     digit_response = ""

        #     # skip the initial non-digit characters
        #     encountered_digit = False

        #     for char in orig_response:
        #         if char.isdigit():
        #             encountered_digit = True
        #             digit_response += char
        #         else:
        #             if encountered_digit:
        #                 break

        # try:
        #     if self.tools:
        #         json_response = json.loads(orig_response)
        #         if self.debug:
        #             print(json_response)
        #         digit_response = json_response['action']

        #     end_time = time.time()
        #     if self.debug:
        #         print(f"response time: {end_time - start_time}")

        #     if int(digit_response) == 0:
        #         action = (-1, (0, 0), (0, 0), 0, 0)
        #     else:
        #         action = info['available_moves'][int(digit_response) - 1]
        # except Exception as e:
        #     print(e)
        #     print(f"unusual response: {orig_response}")
        #     action = random.choice(info['available_moves']) # assign random action instead
        arguments = json.loads(chat_completion.choices[0].message.function_call.arguments)
        print(arguments)
        action = arguments["action_id"]
        try :
            description = arguments["description"]
        except:
            description = ""
        try :
            explanation = arguments["explanation"]
        except:
            explanation = ""
        if not is_conversation:
            self.update_summary(state, info, action, description, explanation, is_conversation=False, players=players)
        content = None
        if action < 0:
            if action != -3:
                content = arguments["content"]
        else:
            if action == 0:
                action = (-1, (0, 0), (0, 0), 0, 0)
            else :
                action = info['available_moves'][int(action) - 1]
        return (action, description, content)

    def dndenv_state_to_prompt(self, state, info, players=None):
        player_positions = {}
        self_position = None
        for el in players:
            if el[2].name == self.name:
                self_position = (el[3][1], el[3][0])
        assert(self_position != None)
        for el in players:
            player_positions[(el[3][1] - self_position[0], el[3][0] - self_position[1])] = el[2].name
        map = state["map"]
        actions, bonus_actions, reactions = state["turn_info"]
        player_type = state["player_type"][0]
        entity_mappings = info["entity_mappings"]
        # swap values to keys for entity mappings
        entity_mappings = {v: k for k, v in entity_mappings.items()}
        player_type_str = entity_mappings.get(player_type, "")
        player_type_str, player_level = player_type_str.split("-")
        health_pct = state["health_pct"]
        movement = state["movement"]
        conditions = state["conditions"]
        is_prone, is_dodging, is_grappled, is_disengaging, _, _, _, _ = conditions

        instruction_prompt = "We are playing a game of Dungeons and Dragons 5th Edition. It is current your turn and you play \n" + \
                             f"as a hero character denoted by {self.name[0]} (a level {player_level} {player_type_str})."
        instruction_prompt += f"Your health is at {health_pct*100}% specifically {info['health']}/{info['max_health']} \n"
        instruction_prompt += "Your current conditions are:\n"
        if is_prone:
            instruction_prompt += "Currently Prone\n"

        if is_dodging:
            instruction_prompt += "Currently Dodging\n"

        if is_disengaging:
            instruction_prompt += "Currently Disengaging\n"
        
        
        
        enemy_types = state["enemy_type"]
        health_enemy = state["health_enemy"]
        instruction_prompt += f"\nYou have as enemies :"
        for i, name in enumerate(state["enemy_name"]):
            is_enemy_prone, is_enemy_dodging, is_enemy_grappled, is_enemy_disengaging, _, _, _, _  = state["enemy_conditions"][i]
            enemy_type_str = entity_mappings.get(enemy_types[i], "")
            enemy_type_str, enemy_level = enemy_type_str.split("-")
            instruction_prompt += f"\n - {name} denoted by {name[0]} (a level {enemy_level} {enemy_type_str}).\n    Their health is currently at {health_enemy[i]*100}%."
            instruction_prompt += "\n    Their current conditions are: "
            if is_enemy_prone:
                instruction_prompt += "Currently Prone, "

            if is_enemy_dodging:
                instruction_prompt += "Currently Dodging, "

            if is_enemy_disengaging:
                instruction_prompt += "Currently Disengaging"
        instruction_prompt += "\nYou must defeat all of them in order to win.\n\n"


        ally_types = state["ally_type"]
        health_ally = state["health_ally"]
        if len(ally_types) > 0:
            instruction_prompt += f"You are helped in that regard by your allies :"
            for i, name in enumerate(state["ally_name"]):
                is_ally_prone, is_ally_dodging, is_ally_grappled, is_ally_disengaging, _, _, _, _  = state["ally_conditions"][i]
                ally_type_str = entity_mappings.get(ally_types[i], "")
                ally_type_str, ally_level = ally_type_str.split("-")
                instruction_prompt += f"\n - {name} denoted by {name[0]} (a level {ally_level} {ally_type_str}).\n    Their health is currently at {health_ally[i]*100}%."
                instruction_prompt += "\n    Their current conditions are: "
                if is_ally_prone:
                    instruction_prompt += "Currently Prone, "

                if is_ally_dodging:
                    instruction_prompt += "Currently Dodging, "

                if is_ally_disengaging:
                    instruction_prompt += "Currently Disengaging"

        instruction_prompt += "You have the following available actions and movement available:\n\n"
        instruction_prompt += f"Available movement: {movement}ft\n"
        instruction_prompt += f"Available actions: {actions}\n"
        instruction_prompt += f"Bonus actions: {bonus_actions}\n"
        instruction_prompt += f"Reactions: {reactions}\n\n"
        spell_slots = state["spell_slots"]
        for level, slots in enumerate(spell_slots):
            if slots > 0:
                instruction_prompt += f"Spell Slot Level {level + 1}: {slots} slots\n"
        
        instruction_prompt += "\nNote that discussions are cheap actions and you should therefore not hesitate to communicate once every few round with your allies to corrdinate plans or update them. Although there is no need to chat arounf if you already coordinated.\n"
        

        prompt = instruction_prompt
        prompt += self.map_to_prompt(map, player_positions)
        prompt += "\n Here is a shirt summary of what happened previously :\n"
        prompt += self.summary
        prompt += "\n"

        if info.get('trigger', False):
            prompt += f"Note that this is not really your turn but a Reaction for {info['trigger']}:"
        prompt += actions_to_prompt(info['available_moves'], info["weapon_mappings"], info["spell_mappings"], player_positions)
        prompt += "-1: communicate with my allies\n"
        
        return prompt

    def action_prompting(self):
        prompt = ""
        prompt += "\n\nPlease choose what you want to do in this situation by using the JSON format given to you before."
        return prompt

    def communication_prompting(self, include_answer_prompting = True):
        prompt = ""
        prompt += "This is not really your turn but rather an ongoing discussion between your allies. Here is the content of the discussion so far :"
        for speaker, content in self.ongoing_conversation:
            prompt += f"\n\n{speaker} : {content}"
        if include_answer_prompting:
            prompt += "\n\nSince this is a conversation, please choose what you want to say in the current situation or if you want to pass the communication. I you deem that you have no more information to exchange or that you are not concerned by the conversation, do not hesitate to simply pass. No action have been performed since the start of the conversation so once you have figured a plan you need to pass the conversation in order to perform it. The corresponding actions are\n- -3 : Pass/end the communication\n- -2 : Answer the communication"
        return prompt
    
    def register_conversation(self, sender, content):
        self.ongoing_conversation.append((sender, content))
    
    def initiate_conversation(self):
        self.ongoing_conversation = []
    
    def close_conversation(self, state, info, players):
        self.update_summary(state, info, None, None, None, True, players)
    
    def update_summary(self, state, info, action, description, explanation, is_conversation, players=None):
        state_prompt = self.dndenv_state_to_prompt(state, info, players=players)
        if not is_conversation:
            prompt = state_prompt + f"In this situation you chose to perform the action:\n{action}: {description}\nYour reasonning being : {explanation}"
        else:
            prompt = state_prompt + self.communication_prompting(include_answer_prompting=False) + f"\nThis conversation has now been concluded."
        
        # measure gpt-4o response time
        start_time = time.time()

        summary_prompt = f"In the previous message, you can see the current state and decisions that the player '{self.name}' and his party took while playing a Dungeon and Dragon combat encounter. Please rewrite the following summary of '{self.name}' situation in order to accomodate for the evolution of the situation. Give particular care to the intentions and future plans that were announced.\n\nThe original summary was :\n{self.summary}"

        if self.debug:
            print(f"Summary prompt: -------------------------------\n{prompt}\n---------------------------------\n\n\n{summary_prompt}\n---------------------------------")
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are the internal voice of a player of Dungeon and Dragon. When given a summary of the previous situation of that player along with the current state and it's most recent decision or conversation, you rewrite the previous summary so as to remove the informations that are no longer true or relevant and add the new informations.\nYou do not need to keep track of any specific number or position but instead focus on the internal chain of thoughs of the player so that you can keep track of what was his and his allies plan.\n\nYou only answer by giving the rewritten summary and no other interaction or explanation."
                },
                {
                    "role": "user",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": summary_prompt,
                }
            ],
            model=self.variant,
            functions = self.functions,
            function_call = {
                "name": "rewrite_summary"
            }
        )
        arguments = json.loads(chat_completion.choices[0].message.function_call.arguments)
        self.summary = arguments["summary"]















class GPT4Interfacer(LLMInterfacer):
    def __init__(self, variant="NousResearch/Meta-Llama-3-8B-Instruct", debug=False, api_key=None, base_url=None, tools=False, explain=False, weapon_mappings=None, max_retries=4):
        """
        Args:
            api_key: the openai api key to use
            variant: the variant of the model to use, e.g. gpt-4o, gpt-4, etc.
            debug: whether to print debug information
        """
        super().__init__(debug, explain=explain)

        if api_key is None and base_url is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key is None:
                raise ValueError("Please set the OPENAI_API_KEY environment variable")
        self.variant = variant
        self.debug = debug
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries
        )
        if tools:
            self.tools = [
                {
                    "type": "function",
                    "function": {
                    "name": "get_action",
                    "description": "get action for agent to execute",
                    "parameters": {
                        "type": "object",
                        "properties": {
                        "action": {
                            "type": "integer",
                            "description": "action to take",
                        }
                        },
                        "required": ["action"],
                    },
                    }
                }
            ]
        else:
            self.tools = None
    
    def select_action_for_state(self, state, info):
        prompt = self.dndenv_state_to_prompt(state, info)
        # measure gpt-4o response time
        start_time = time.time()

        if self.debug:
            print(f"prompt: -------------------------------\n{prompt}\n---------------------------------")
        if self.tools:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.variant,
                tools=self.tools,
                tool_choice="required"
            )
        else:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.variant
            )
        
        if self.tools:
            orig_response = chat_completion.choices[0].message.tool_calls[0].function.arguments
            
        else:
            orig_response = chat_completion.choices[0].message.content
            digit_response = ""

            # skip the initial non-digit characters
            encountered_digit = False

            for char in orig_response:
                if char.isdigit():
                    encountered_digit = True
                    digit_response += char
                else:
                    if encountered_digit:
                        break

        try:
            if self.tools:
                json_response = json.loads(orig_response)
                if self.debug:
                    print(json_response)
                digit_response = json_response['action']

            end_time = time.time()
            if self.debug:
                print(f"response time: {end_time - start_time}")

            if int(digit_response) == 0:
                action = (-1, (0, 0), (0, 0), 0, 0)
            else:
                action = info['available_moves'][int(digit_response) - 1]
        except Exception as e:
            print(e)
            print(f"unusual response: {orig_response}")
            action = random.choice(info['available_moves']) # assign random action instead
        return action


class LLama3Interface(LLMInterfacer):
    def __init__(self, url, debug=False):
        super().__init__(debug)
        self.url = url

    def select_action_for_state(self, state, info):
        prompt = self.dndenv_state_to_prompt(state, info)
        # measure gpt-4o response time
        start_time = time.time()

        if self.debug:
            print(f"prompt: -------------------------------\n{prompt}\n---------------------------------")
        #chat_completion = self.client.chat.completions.create(
        #    messages=[
        #        {
        #            "role": "user",
        #            "content": prompt,
        #        }
        #    ],
        #    model="gpt-4o",
            
            # add the action function to the completion
        #   tools=tools,
        #    tool_choice="required"
        #)
        
        #response = chat_completion.choices[0].message.content
        # import json
        # Example usage
        regex = "\d"

        json_response = self._generate_text_with_regex(prompt, regex)

        #json_response = chat_completion.choices[0].message.tool_calls[0].function.arguments#json.loads(chat_completion.choices[0].message.function_call.arguments)
        #json_response = json.loads(json_response)
        response = self._extract_last_number(json_response['text'][0])

        #response = json_response['action']
        
        end_time = time.time()
        if self.debug:
            print(f"response time: {end_time - start_time}")
            print(f"response: {response}")
        # parse the response and return the action
        # e.g. 1: attack enemy with ranged weapon or Let's proceed with option [4], or just extract the first number
        # from the response

        #for char in response:
        #    if char.isdigit():
        #        response = char
        #        break 

        try:
            print(f"response: {response}")
            if int(response) == 0:
                action = (-1, (0, 0), (0, 0), 0, 0)
            else:
                action = info['available_moves'][int(response) - 1]
        except Exception as e:
            print(e)
            print(f"unusual response: {response}")
            action = random.choice(info['available_moves']) # assign random action instead
        return action
    
    def _generate_text_with_regex(self, prompt, regex):
        data = {
            "prompt": prompt,
            "regex": regex
        }
        
        response = requests.post(self.url, json=data)
        print(response)
        if response.status_code == 200:
            return response.json()
        else:
            print(response.text)
            return None

    def _extract_last_number(self, text):
        # Regular expression to match numbers
        #number_regex = r'-?\d+(\.\d+)?'
        
        # Find all matches in the text
        text = text.split(".")[-1]
        #print("hello: ",text)

        # matches = re.findall(number_regex, text)
        
        # Return the last match or None if no match is found
        #return matches if matches else None
        return int(text)


        


    


        