from natural20.gym.tools import compute_available_moves


class Experiment():
    def __init__(self, environment, dnd_environment, agents, conversational_groups, debug=False):
        self.env = environment
        self.dnd_environment = dnd_environment
        self.agents = agents
        self.debug = debug
        self.conversational_groups = conversational_groups
        self.backlog = []
        self.conversations = []
        self.finished = False
        self.current_step = 0
    
    def get_obs_inf(self, player):
        p_observation = self.dnd_environment.generate_observation(player)
        p_available_moves = compute_available_moves(self.dnd_environment.session, self.dnd_environment.map, player, self.dnd_environment.battle, self.dnd_environment.weapon_mappings, self.dnd_environment.spell_mappings)
        p_info = self.dnd_environment._info(p_available_moves, player)
        return p_observation, p_info
    
    def update_all_agents(self, agents_name, sender, content):
        for name in agents_name:
            self.agents[name][0].register_conversation(sender, content)
        self.conversations[-1].append((sender, content))

    def initiate_conversation(self, agents_name):
        for name in agents_name:
            self.agents[name][0].initiate_conversation()
        self.conversations.append([])

    def close_conversation(self, agents_name):
        for name in agents_name:
            obs, inf = self.get_obs_inf(self.agents[name][2])
            self.agents[name][0].close_conversation(obs, inf, self.get_players_pos())
        self.conversations[-1].append((None, "Conversation closed"))

    def run_conversation(self, sender, content):
        sender_gr = self.agents[sender][1]
        if not self.conversational_groups[sender_gr]:
            raise ValueError(f"The agent {sender} from the non conversational group {sender_gr} tried to initiate a conversation")
        agent_in_the_conv = []
        for name, (_, gr, _) in self.agents.items():
            if sender_gr == gr and name != sender:
                agent_in_the_conv.append(name)
        agent_in_the_conv.append(sender)
        self.initiate_conversation(agent_in_the_conv)
        self.update_all_agents(agent_in_the_conv, sender, content)
        conv_alive = True
        conv_step = 0
        while conv_alive:
            conv_step += 1
            conv_alive = False
            for name in agent_in_the_conv:
                obs, inf = self.get_obs_inf(self.agents[name][2])
                action, descrition,  content = self.agents[name][0].select_action_for_state(obs, inf, self.get_players_pos(), is_conversation=True)
                if action == -2:
                    self.update_all_agents(agent_in_the_conv, name, content)
                    conv_alive = True
                elif action != -3:
                    raise ValueError(f"A non conversation action {action} was used during a conversation by agent {name}")
        self.close_conversation(agent_in_the_conv)
    
    def step(self):
        current_agent, current_group, current_character = self.agents[self.dnd_environment.battle.current_turn().name]
        obs, inf = self.get_obs_inf(current_character)
        # Manual removala of help action since it crashes
        help_index = []
        for i, el in enumerate(inf["available_moves"]):
            if el[0] == 14:
                help_index.append(i)
        for index in help_index[::-1]:
            inf["available_moves"].pop(index)
        
        action, descrition, content = current_agent.select_action_for_state(obs, inf, self.get_players_pos())
        if self.debug:
            print(f"The chosen action is : {action}")
        self.backlog.append((current_character.name, action, descrition))
        if action != -1:
            _, _, terminal, _, _ = self.env.step(action)
        else :
            self.backlog.append((current_character.name, -1, len(self.conversations)))
            self.run_conversation(sender=current_character.name, content=content)
            terminal = False
        return terminal
    
    def get_players_pos(self):
        return {player: self.dnd_environment.battle.maps[0].entity_or_object_pos(player) for (_, _, player) in self.agents.values()}
    
    def run_till_end(self, max_step= 30):
        done = False
        while not done and self.current_step < max_step:
            print(f"Starting step {self.current_step}/{max_step}", end="\r")
            if self.debug:
                health = []
                for player, pos in self.get_players_pos().items():
                    health.append(player.health_percent())
                    print(f"Player {player.name} has {player.health_percent()}% life points, {pos}")
            done = self.step()
            self.current_step += 1
        self.finished = self.dnd_environment.battle.battle_ends() or (self.current_step >= max_step)
        return self.finished