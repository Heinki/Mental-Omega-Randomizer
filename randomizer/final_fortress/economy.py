"""Fortress-only passive income using native timers and Ares credit deposits."""

from randomizer.maps.buff_values import _register_map_type
from randomizer.maps.ini import section_value_map


FUNDRAISING_INTERVAL_SECONDS = 300
FUNDRAISING_CREDITS_PER_STACK = 1000
FUNDRAISING_MAX_STACKS = 4


def validate_fundraising_ranks(values, count):
    if (not isinstance(values, (list, tuple)) or len(values) != count
            or any(type(value) is not int or not 0 <= value <= FUNDRAISING_MAX_STACKS
                   for value in values)):
        raise ValueError('Fundraising requires one rank from 0 to 4 per human player.')


def selected_fundraising_rank(state):
    """Disabled purchases contribute nothing to the next frozen run."""
    return (state['perk_ranks'].get('fundraising', 0)
            if 'fundraising' in state['selected_perks'] else 0)


def apply_fundraising(writer, plan, rules, finished):
    """One repeating elapsed-time event per recipient, independent of rank.

    Action 33 grants an immediately ready, one-shot Ares power. Its positive
    Money.Amount credits the firing house directly. The harmless warhead has
    no animation, damage or spawned objects, and needs no launch building.
    Repeating tags reset the native elapsed-time event after each payment;
    the finished flag prevents further grants after victory or objective loss.
    Ranks are frozen before launch, as for every other Fortress perk.
    """
    if plan.get('plan_version', 1) < 34:
        return
    from .engine import _action
    from .player_perks import coalition

    personal = plan['fundraising_ranks']
    validate_fundraising_ranks(personal, len(plan.get('coop_players', [])) or 1)
    if not any(personal):
        return
    warhead = writer.key()
    writer.sections[warhead] = {
        'Verses': '0%,0%,0%,0%,0%,0%,0%,0%,0%,0%,0%',
        'AnimList': 'none', 'CellSpread': '0', 'Wall': 'no', 'Wood': 'no',
        'Sparky': 'no', 'Tiberium': 'no', 'Rocker': 'no',
    }
    _register_map_type(writer.sections, writer.lines, rules, 'Warheads', warhead)
    for slot, (actor, _, _) in enumerate(coalition(plan)):
        stacks = personal[slot] if slot < len(personal) else personal[0]
        if not stacks:
            continue
        power = writer.key()
        writer.sections[power] = {
            'Name': 'Final Fortress Fundraising ' + actor, 'UIName': 'NOSTR:Fundraising',
            'Type': 'GenericWarhead', 'Action': 'None', 'RechargeTime': '0',
            'IsPowered': 'no', 'DisableableFromShell': 'no', 'ShowTimer': 'no',
            'SW.RequiredHouses': actor, 'SW.InitialReady': 'yes',
            'SW.AutoFire': 'yes', 'SW.ManualFire': 'no', 'SW.ShowCameo': 'no',
            'SW.AITargeting': 'Base', 'SW.AITargeting.Constraints': 'none',
            'SW.AITargeting.Preference': 'none', 'SW.AllowPlayer': 'yes', 'SW.AllowAI': 'yes',
            'SW.Damage': '0', 'SW.Warhead': warhead, 'SW.CreateRadarEvent': 'no',
            'EVA.Ready': 'none', 'EVA.Activated': 'none', 'EVA.Detected': 'none',
            'Message.Detected': 'NOSTR:',
            'Money.Amount': str(stacks * FUNDRAISING_CREDITS_PER_STACK),
        }
        _register_map_type(writer.sections, writer.lines, rules, 'SuperWeaponTypes', power)
        registered = list(dict.fromkeys([
            *rules['SuperWeaponTypes'].values(),
            *section_value_map(writer.lines, 'SuperWeaponTypes').values(),
            *writer.sections['SuperWeaponTypes'].values()]))
        trigger, _ = writer.trigger('Fortress Fundraising ' + actor,
            [(13, 0, FUNDRAISING_INTERVAL_SECONDS), (37, 0, finished)],
            [_action(33, registered.index(power))], owner=actor, persistence=2)
        writer.put('FFFundraising', actor, f'{power},{stacks},{trigger}')
