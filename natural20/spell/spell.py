import re

def camel_case_to_human_readable(camel_case_string):
    # Insert spaces before uppercase letters and capitalize the first letter
    human_readable = re.sub(r'(?<!^)(?=[A-Z])', '_', camel_case_string).capitalize()
    return human_readable.lower()

def consume_resource(battle, source, item, as_scroll=False):
    amt, resource = item["casting_time"].split(":")
    spell_level = item["level"]

    if battle:
        if source.familiar():
            # consume bonus action from familiar
            battle.consume(source, "reaction")
            source = source.owner

        if resource == "action":
            battle.consume(source, "action")
        elif resource == "reaction":
            battle.consume(source, "reaction")
        elif resource == "bonus_action":
            battle.consume(source, "bonus_action")

        # track spell casted
        if spell_level > 0 and resource in ["action", "bonus_action"]:
            battle.entity_state_for(source)['casted_level_spells'].append(item)

    # scrolls do not consume spell slots
    if not as_scroll:
        if source.familiar():
            source.owner.consume_spell_slot(spell_level) if spell_level > 0 else None
        else:
            source.consume_spell_slot(spell_level) if spell_level > 0 else None

class AttackHook:
    def after_attack_roll(battle, entity, attacker, attack_roll, effective_ac, opts=None):
        pass

class Spell:
    def __init__(self, session, source, spell_name, details):
        self.session = session
        self.name = spell_name
        self.properties = details
        self.action = None
        self.source = source
        self.target = None
        self.errors = []
        self.attack_roll = None

    def short_name(self):
        # remove the spell suffix and turn Camelcase to space separated
        return camel_case_to_human_readable(self.name[:-5])
    
    def __str__(self):
        return camel_case_to_human_readable(self.name[:-5]).replace(" ", "_")

    def label(self):
        return self.properties.get('label', self.short_name())

    def clone(self):
        spell = self.__class__(self.session, self.source, self.name, self.properties)
        spell.target = self.target
        spell.action = self.action
        return spell

    @property
    def id(self):
        return self.properties.get('id')

    def consume(self, battle, as_scroll=False):
        consume_resource(battle, self.source, self.properties, as_scroll=as_scroll)

    @staticmethod
    def apply(battle, item, session=None):
        pass

    def validate(self, battle_map, target=None):
        self.errors.clear()

    def load_spell_info(self):
        return self.session.load_spell(self.name)

    def t(self, token, spell=None, options=None):
        if options is None:
            options = {}
        return token

    def compute_advantage_info(self, battle, opts=None):
        return 0, [[],[]], 0

    def compute_hit_probability(self, battle, opts = None):
        return 1.0

    def avg_damage(self, battle, opts=None):
        return 0
    
    def to_dict(self):
        return {
            'name': self.name,
            'session': self.session,
            'properties': self.properties,
            # 'source': self.source,
            # 'target': self.target,
            # 'action': self.action
        }
    
    @staticmethod
    def from_dict(data):
        return Spell(data['session'], None, data['name'], data['properties'])
