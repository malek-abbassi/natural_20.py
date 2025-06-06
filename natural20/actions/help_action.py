from natural20.action import Action

class HelpAction(Action):
    target: any

    def __init__(self, session, source, action_type, opts=None):
        super().__init__(session, source, action_type, opts)
        self.target = None

    @staticmethod
    def can(entity, battle):
        if battle:
            return entity.total_actions(battle) > 0
        return True

    def build_map(self):
        def set_target(target):
            self.target = target
            return self
        return {
            'action': self,
            'param': [
                {
                    'type': 'select_target',
                    'target_types': ['allies', 'enemies'],
                    'range': 5,
                    'num': 1
                }
            ],
            'next': set_target
        }

    @staticmethod
    def build(session, source):
        action = HelpAction(session, source, 'help')
        return action.build_map()

    def resolve(self, session, map, opts=None):
        if not opts:
            opts = {}

        current_battle = opts.get('battle')
        self.result = [{
            'source': self.source,
            'target': self.target,
            'type': 'help',
            'battle': current_battle
        }]
        return self

    @staticmethod
    def apply(battle, item, session=None):
        if item['type'] != 'help':
            return

        source = item['source']
        target = item['target']
        event_manager = battle.event_manager if battle else session.event_manager

        if battle:
            battle.consume(source, 'action')
            event_type = 'help_distract' if battle.opposing(source, target) else 'help'
            if event_type == 'help_distract':
                battle.do_distract(source, target)
            else:
                source.do_help(battle, target)
        else:
            source.do_help(None, target)

        event_manager.received_event({
            'source': source,
            'target': target,
            'event': event_type if battle else 'help'
        })
