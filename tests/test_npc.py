import unittest
from natural20.map import Map
from natural20.battle import Battle
from natural20.actions.attack_action import AttackAction
from natural20.utils.action_builder import autobuild
from natural20.session import Session
from natural20.map_renderer import MapRenderer
from natural20.event_manager import EventManager
from natural20.player_character import PlayerCharacter
from natural20.entity import Entity
from natural20.die_roll import DieRoll
import random
import pdb
class TestNpc(unittest.TestCase):
    def make_session(self):
        event_manager = EventManager()
        event_manager.standard_cli()
        return Session(root_path='tests/fixtures', event_manager=event_manager)
    
    def setUp(self) -> None:
        self.session = self.make_session()
        self.map = Map(self.session, 'tests/fixtures/battle_sim.yml')
        self.session.register_map('test_map', self.map)
        random.seed(7003)
        return super().setUp()

    def test_stench_effect(self):
        battle = Battle(self.session, self.map)
        fighter = PlayerCharacter.load(self.session, 'high_elf_fighter.yml')
        battle.add(fighter, 'a', position=[1, 1], token='G')
        fighter.reset_turn(battle)
        npc = self.session.npc('ghast')
        battle.add(npc, 'b', position=[2, 2])
        battle.start()
        print(MapRenderer(battle.map_for(npc), battle).render())
        self.assertFalse(fighter.poisoned())
        battle.set_current_turn(fighter)
        DieRoll.fudge(1)
        battle.start_turn()
        print(MapRenderer(battle.map_for(npc), battle).render())
        self.assertTrue(fighter.poisoned())
        self.map.move_to(fighter, 0, 1, battle=battle)
        fighter.reset_turn(battle)
        battle.start_turn()
        print(MapRenderer(battle.map_for(npc), battle).render())
        self.assertFalse(fighter.poisoned())

    def test_engulf_effect(self):
        battle = Battle(self.session, self.map)
        fighter = PlayerCharacter.load(self.session, 'high_elf_fighter.yml')
        battle.add(fighter, 'a', position=[0, 1], token='G')
        fighter.reset_turn(battle)
        npc = self.session.npc('shamblingmound')
        self.map.add(npc, 1, 0)
        battle.add(npc, 'b')
        npc.reset_turn(battle)
        print(MapRenderer(battle.map_for(npc), battle).render())
        action = autobuild(self.session, AttackAction, npc, battle, map=battle.map_for(npc), match=['engulf', fighter])[0]
        battle.action(action)
        battle.commit(action)
        self.assertTrue(fighter.grappled())
        print(MapRenderer(battle.map_for(npc), battle).render())
        print(MapRenderer(battle.map_for(fighter), battle).render())
        npc.make_dead()
        print(MapRenderer(battle.map_for(npc), battle).render())
        print(MapRenderer(battle.map_for(fighter), battle).render())

    def test_legendary_actions(self):
        battle = Battle(self.session, self.map)
        fighter = PlayerCharacter.load(self.session, 'high_elf_fighter.yml')
        battle.add(fighter, 'a', position=[0, 1], token='G')
        fighter.reset_turn(battle)
        npc = self.session.npc('shamblingmound')
        self.map.add(npc, 1, 0)
        battle.add(npc, 'b')
        npc.reset_turn(battle)
        print(MapRenderer(battle.map_for(npc), battle).render())
        actions = npc.available_actions(self.session, battle, legendary_actions=True)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].name(), 'attack')

    def test_consecutive_multiattack(self):
        battle = Battle(self.session, self.map)
        fighter = PlayerCharacter.load(self.session, 'high_elf_fighter.yml')
        battle.add(fighter, 'a', position=[0, 1], token='G')
        npc = self.session.npc('shamblingmound')
        self.map.add(npc, 1, 0)
        battle.add(npc, 'b', add_to_initiative=True)
        npc.reset_turn(battle)
        battle.set_current_turn(npc)
        print(MapRenderer(battle.map_for(npc), battle).render())
        action = npc.available_actions(self.session, battle)
        action_str = [str(a) for a in action]
        self.assertEqual(action_str, ['Shamblingmound uses slam on Gomerin',
        'Shamblingmound uses slam2 on Gomerin',
        'Shamblingmound uses engulf on Gomerin',
        'Shamblingmound uses bone_splinter on Gomerin',
        'Dash',
        'Disengage',
        'Hide',
        'Dodge',
        'Look',
        'move to [1, 1]',
        'Shove',
        'Help'])
        self.assertEqual(len(action), 12)

    def test_npc(self):
        session = self.make_session()

        # skeleton npc
        npc = session.npc('skeleton')
        assert npc.damage_vulnerabilities == ['bludgeoning']

        # bat npc
        battle_map = Map(session, 'tests/fixtures/battle_sim.yml')
        npc = session.npc('bat', { "name" : 'Screech', "familiar" : True })
        battle = Battle(session, battle_map)
        battle.add(npc, 'b', position=[1, 1])
        npc.land()
        assert npc.speed() == 5

        npc.fly()
        assert npc.speed() == 30
        assert npc.flying

        assert npc.can_fly()

        map_render = MapRenderer(battle_map, battle)
        assert map_render.render() == (
            "g···#·\n"
            "·v·##·\n"
            "····#·\n"
            "······\n"
            "·##oo·\n"
            "·····Î\n"
            "·····A\n"
        ), map_render.render()

        npc.take_damage(100, battle=battle)
        self.assertMultiLineEqual(map_render.render(),
            "g···#·\n"
            "·`·##·\n"
            "····#·\n"
            "······\n"
            "·##oo·\n"
            "·····Î\n"
            "·····A\n"
        )

        # goblin npc
        npc = session.npc('goblin', { "name" : 'Spark'})
        battle = Battle(session, battle_map)
        battle.add(npc, 'a', position=[2, 2])
        battle.start()
        self.assertTrue(npc.any_class_feature(['nimble_escape', 'cunning_action']))
        assert npc.darkvision(60)
        assert 2 <= npc.hp() <= 12
        assert npc.name == 'Spark'
        assert npc.armor_class() == 15
        assert npc.passive_perception() == 9
        assert [item["name"] for item in npc.equipped_items()] == ['scimitar', 'shortbow', 'leather_armor', 'shield']

        npc.unequip('scimitar')
        assert not npc.equipped('scimitar')
        assert npc.item_count('scimitar') > 0

        npc.unequip('scimitar')
        assert not npc.equipped('scimitar')
        npc.equip('scimitar')
        assert npc.equipped('scimitar')
        npc.reset_turn(battle)
        battle.set_current_turn(npc)
        available_actions = [str(action) for action in npc.available_actions(session, battle, map=battle_map)]
        assert len(available_actions) == 17, len(available_actions)

        self.assertListEqual(available_actions, ["Dash",
                                                 "Disengage",
                                                 "Disengage_bonus",
                                                 "Hide",
                                                 "Hide_bonus",
                                                 "Dodge",
                                                 "Look",
                                                 "move to [1, 2]",
                                                 "move to [1, 3]",
                                                 "move to [2, 1]",
                                                 "move to [2, 3]",
                                                 "move to [3, 2]",
                                                 "move to [3, 3]",
                                                 "Shove",
                                                 "Help",
                                                 "Interact(Screech,loot)",
                                                 "Interact(Ground,pickup_drop)"
                                                 ])

        assert npc.hit_die() == {6: 2}, npc.hit_die()

        random.seed(7000)
        npc.take_damage(4, session=session)
        assert npc.hit_die() == {6: 2}
        npc.short_rest(battle)
        assert npc.hp() == 6, npc.hp()
        assert npc.hit_die() == {6: 1}

        result = [npc.save_throw(attribute) for attribute in Entity.ATTRIBUTE_TYPES]
        assert [dr.roller.roll_str for dr in result] == ['d20-1', 'd20+2', 'd20+0', 'd20+0', 'd20-1', 'd20-1']

        roll = npc.stealth_check(battle)
        assert roll.roller.roll_str == '1d20+6'

        self.assertEqual(npc.apply_effect('status:prone'),{'battle': None,
                                                           'source': npc,
                                                           'type': 'prone',
                                                           'context' : {},
                                                           'flavor': None})

        # owlbear npc
        npc = session.npc('owlbear', { "name" : 'Grunt'})
        battle = Battle(session, battle_map)
        fighter = PlayerCharacter.load(session, 'high_elf_fighter.yml')
        battle.add(fighter, 'a', position=[0,5], token='G')
        battle.add(npc, 'b', position='spawn_point_2', token='G')
        npc.reset_turn(battle)
        fighter.reset_turn(battle)
        battle.start()

        self.assertTrue(npc.darkvision(60))

        self.assertEqual(len(npc.available_actions(session, None, map=battle_map)), 6)
        available_actions = [action.name() for action in npc.available_actions(session, None, map=battle_map)]
        self.assertEqual(available_actions, ['attack', 'attack', 'look', 'move', 'shove', 'help'])
        battle.set_current_turn(npc)
        first_attack = [a for a in npc.available_actions(session, battle, map=battle_map) if a.name() == 'attack'][0]
        first_attack.target = fighter
        battle.action(first_attack)
        battle.commit(first_attack)

        available_actions = [action.name() for action in npc.available_actions(session, battle)]

        assert available_actions == ['attack', 'move'], available_actions
