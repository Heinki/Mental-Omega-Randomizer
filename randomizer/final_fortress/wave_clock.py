"""A separate native recharge display synchronized with enemy wave delivery."""

from copy import deepcopy

from randomizer.maps.buff_values import _register_map_type
from randomizer.maps.ini import section_value_map


def create_wave_clock(writer, plan, rules, finished):
    from .engine import _action, _place
    from .player_perks import needs_countries

    if plan.get('plan_version', 1) < 17 or not plan['wave_schedule']:
        return None
    power = writer.key()
    owner = 'FFPLAYER' if needs_countries(plan) else plan['player_country']
    writer.sections[power] = {
        'Name': 'Final Fortress next enemy wave', 'UIName': 'NOSTR:Next enemy wave',
        'Type': 'GenericWarhead', 'Action': 'None', 'RechargeTime': f'{plan["wave_interval_seconds"] / 60:g}',
        'IsPowered': 'no', 'ShowTimer': 'yes', 'DisableableFromShell': 'no',
        'SW.TimerVisibility': 'owner', 'SW.RequiredHouses': owner,
        'SW.AllowPlayer': 'yes', 'SW.AllowAI': 'no', 'SW.InitialReady': 'no',
        'SW.AutoFire': 'yes', 'SW.ManualFire': 'no', 'SW.ShowCameo': 'no',
        'SW.AITargeting': 'None', 'SW.Damage': '0', 'SW.Warhead': 'SA',
        'SW.CreateRadarEvent': 'no', 'EVA.Ready': 'none', 'EVA.Activated': 'none',
        'EVA.Detected': 'none', 'SW.ActivationSound': 'none',
    }
    _register_map_type(writer.sections, writer.lines, rules, 'SuperWeaponTypes', power)
    registered = list(dict.fromkeys([
        *rules['SuperWeaponTypes'].values(),
        *section_value_map(writer.lines, 'SuperWeaponTypes').values(),
        *writer.sections['SuperWeaponTypes'].values()]))
    index = registered.index(power)
    restart = writer.flag('Wave clock restart')
    done = writer.flag('Wave clock finished')
    reset, _ = writer.trigger('Wave clock reset', [(36, 0, restart), (37, 0, finished)],
                             [_action(134, index), _action(57, restart)], owner=owner, persistence=2)
    writer.trigger('Wave clock end of run', [(36, 0, finished)], [_action(56, done)])
    # Keep the attachment after its linked ownership event, as for the Lab's
    # persistent ownership/loss tag. A one-shot tag could disappear at startup.
    remove, tag = writer.trigger('Wave clock remove', [(36, 0, done)], [], persistence=2)
    writer.put('Actions', remove, '2,' + ','.join(_action(54, trigger=remove) + _action(32)))
    transfer, _ = writer.trigger('Wave clock ownership', [(13, 0, 0)], [])
    writer.put('Actions', transfer, '2,' + ','.join(
        _action(14, 4475 + plan['map']['player_waypoint']) + _action(54, trigger=transfer)))
    writer.put('Triggers', remove, f'<none>,{transfer},Wave clock remove,0,1,1,1,0')
    provider = writer.key()
    row = deepcopy(rules['CABHUT'])
    row.update(Image='CABHUT', Name='Final Fortress wave clock', InvisibleInGame='yes',
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
    # The reviewed hidden provider row has seven perk-power slots at x106–112.
    # Its next reserved cell supplies the independent clock without occupying
    # any of the human's construction or reinforcement tiles.
    _place(writer, 'Structures', f'Neutral,{provider},256,113,71,64,{tag},1,0,1,0,0,None,None,None,0,0')
    for key, value in dict(Power=power, Index=index, Owner=owner, Provider=provider,
                           Restart=restart, Finished=done, Reset=reset, Remove=remove).items():
        writer.put('FFWaveClock', key, value)
    return restart, done
