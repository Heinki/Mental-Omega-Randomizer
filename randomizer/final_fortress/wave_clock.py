"""A separate native recharge display synchronized with enemy wave delivery."""

from copy import deepcopy

from randomizer.maps.buff_values import _register_map_type
from randomizer.maps.ini import section_value_map


def create_wave_clock(writer, plan, rules, finished):
    from .player_perks import needs_countries
    if plan.get('plan_version', 1) < 17 or not plan['wave_schedule']:
        return None
    owner = 'FFPLAYER' if needs_countries(plan) else plan['player_country']
    return _create_clock(writer, plan, rules, finished, owner=owner,
        waypoint=plan['map']['player_waypoint'], name='Wave clock', label='Next enemy wave',
        first_seconds=plan['wave_interval_seconds'], interval_seconds=plan['wave_interval_seconds'],
        position=plan['map'].get('wave_clock_position', {'x': 113, 'y': 71}), metadata='FFWaveClock')


def create_friendly_clocks(writer, plan, rules, finished):
    """Give each human a countdown following their own reinforcement delivery."""
    from .coop_map import escrow_cell
    from .player_perks import coalition
    from randomizer.maps.ini import section_value_map

    effect = plan['effects'].get('reinforcements')
    if plan.get('plan_version', 1) < 31 or not effect or not plan['reinforcement_schedule']:
        return {}
    occupied = {plan['map']['player_waypoint'], *plan['map']['enemy_waypoints'], *plan['allied_waypoints']}
    spare = next(number for number in range(8) if number not in occupied)
    cell = int(section_value_map(writer.lines, 'Waypoints')[str(spare)])
    clocks = {}
    for owner, _, waypoint in coalition(plan)[:len(plan.get('coop_players', [])) or 1]:
        x, y = escrow_cell(writer, plan, rules, cell)
        metadata = 'FFAlliedClock.' + owner
        clocks[owner] = _create_clock(writer, plan, rules, finished, owner=owner, waypoint=waypoint,
            name='Allied clock ' + owner, label='Next allied reinforcements',
            first_seconds=effect['first_seconds'], interval_seconds=effect['interval_seconds'],
            position={'x': x, 'y': y}, metadata=metadata)
        writer.put('FFAlliedClocks', owner, metadata)
    return clocks


def _create_clock(writer, plan, rules, finished, *, owner, waypoint, name, label,
                  first_seconds, interval_seconds, position, metadata):
    from .engine import _action, _place

    power = writer.key()
    writer.sections[power] = {
        'Name': 'Final Fortress ' + label.lower(), 'UIName': 'NOSTR:' + label,
        'Type': 'GenericWarhead', 'Action': 'None', 'RechargeTime': f'{first_seconds / 60:g}',
        'IsPowered': 'no', 'ShowTimer': 'yes', 'DisableableFromShell': 'no',
        'SW.TimerVisibility': 'owner', 'SW.RequiredHouses': owner,
        'SW.AllowPlayer': 'yes', 'SW.AllowAI': 'no', 'SW.InitialReady': 'no',
        'SW.AutoFire': 'yes', 'SW.ManualFire': 'no', 'SW.ShowCameo': 'no',
        'SW.AITargeting': 'None', 'SW.Damage': '0', 'SW.Warhead': 'SA',
        'SW.CreateRadarEvent': 'no', 'EVA.Ready': 'none', 'EVA.Activated': 'none',
        'EVA.Detected': 'none', 'SW.ActivationSound': 'none',
    }
    if plan.get('plan_version', 1) >= 31:
        # Unlike sound IDs, CSF text needs an explicit empty literal.
        writer.sections[power]['Message.Detected'] = 'NOSTR:'
    _register_map_type(writer.sections, writer.lines, rules, 'SuperWeaponTypes', power)
    registered = list(dict.fromkeys([
        *rules['SuperWeaponTypes'].values(),
        *section_value_map(writer.lines, 'SuperWeaponTypes').values(),
        *writer.sections['SuperWeaponTypes'].values()]))
    index = registered.index(power)
    restart = writer.flag(name + ' restart')
    done = writer.flag(name + ' finished')
    reset_actions = []
    if first_seconds != interval_seconds:
        # FinalAlert's native action 132 takes the recharge duration in frames
        # in its seventh parameter, and applies it on the following reset.
        recharge = _action(132, index, waypoint=str(interval_seconds * 15))
        recharge[1] = '11'  # Native SuperWeapon parameter type (see coop_ecard.map).
        reset_actions.append(recharge)
    reset, _ = writer.trigger(name + ' reset', [(36, 0, restart), (37, 0, finished)],
                             [*reset_actions, _action(134, index), _action(57, restart)], owner=owner, persistence=2)
    writer.trigger(name + ' end of run', [(36, 0, finished)], [_action(56, done)])
    # Keep the attachment after its linked ownership event, as for the Lab's
    # persistent ownership/loss tag. A one-shot tag could disappear at startup.
    remove, tag = writer.trigger(name + ' remove', [(36, 0, done)], [], persistence=2)
    writer.put('Actions', remove, '2,' + ','.join(_action(54, trigger=remove) + _action(32)))
    transfer, _ = writer.trigger(name + ' ownership', [(13, 0, 0)], [])
    writer.put('Actions', transfer, '2,' + ','.join(
        _action(14, 4475 + waypoint) + _action(54, trigger=transfer)))
    writer.put('Triggers', remove, f'<none>,{transfer},{name} remove,0,1,1,1,0')
    provider = writer.key()
    row = deepcopy(rules['CABHUT'])
    row.update(Image='CABHUT', Name='Final Fortress ' + name.lower(), InvisibleInGame='yes',
               IsPassable='yes', Immune='yes', LegalTarget='no', Selectable='no',
               Capturable='no', Unsellable='yes', CanBeOccupied='no', BridgeRepairHut='no',
               Insignificant='no', DontScore='no', KeepAlive='no', RadarInvisible='yes',
               TechLevel='-1', BuildLimit='0', AIBuildThis='no', BaseNormal='no',
               Power='0', Powered='no', SuperWeapon=power, ProduceCashStartup='0',
               ProduceCashAmount='0', ProduceCashDelay='0', ImmuneToPsionics='yes',
               ImmuneToTemporal='yes', ImmuneToEMP='yes', Warpable='no', Sight='0',
               Spyable='no', Drainable='no', Bombable='no')
    row.update(Explosion='none', DestroyAnim='none', DeathWeapon='none', DieSound='none',
               VoiceDie='none', Explodes='no', **{'EVA.Lost': 'none'})
    writer.sections[provider] = row
    _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', provider)
    _place(writer, 'Structures', f'Neutral,{provider},256,{position["x"]},{position["y"]},'
           f'64,{tag},1,0,1,0,0,None,None,None,0,0')
    for key, value in dict(Power=power, Index=index, Owner=owner, Provider=provider,
                           Restart=restart, Finished=done, Reset=reset, Remove=remove).items():
        writer.put(metadata, key, value)
    return restart, done
