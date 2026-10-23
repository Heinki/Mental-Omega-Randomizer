"""One-use objective support attached to the Lab's existing native trigger chain."""

from randomizer.maps.buff_values import _register_map_type
from randomizer.maps.ini import section_value_map, section_value_map_preserve

from .player_perks import coalition, human_actor


def _objective_blast(writer, plan, rules, damage, *, extra_warhead=None):
    """Create a registered instant effect restricted to the private Lab armor."""
    from .engine import _action, _waypoint

    armor, warhead, weapon = 'FFLABARMOR', writer.key(), writer.key()
    if writer.sections['FFOBJECTIVE']['Armor'] != armor:
        writer.put('ArmorTypes', armor, writer.sections['FFOBJECTIVE']['Armor'])
        writer.put('FFOBJECTIVE', 'Armor', armor)
    writer.sections[warhead] = {
        'Verses': ','.join(['0%'] * 11), 'Versus.' + armor: '100%',
        'CellSpread': '3', 'PercentAtMax': '1', 'Wall': 'no', 'Wood': 'no',
        'Conventional': 'no', 'AffectsAllies': 'yes', 'AffectsEnemies': 'yes',
        'AffectsOwner': 'yes', 'PreventScatter': 'yes', **(extra_warhead or {}),
    }
    writer.sections[weapon] = {
        'Damage': str(damage), 'Warhead': warhead, 'Projectile': 'InvisibleAll',
        'ROF': '1', 'Range': '1', 'Speed': '100', 'Report': 'none',
    }
    _register_map_type(writer.sections, writer.lines, rules, 'Warheads', warhead)
    _register_map_type(writer.sections, writer.lines, rules, 'WeaponTypes', weapon)
    # Action 42 takes the native array index, not the INI registration key.
    # Explicit WeaponTypes registrations precede techno loading.
    registered = list(dict.fromkeys([
        *rules['WeaponTypes'].values(),
        *section_value_map_preserve(writer.lines, 'WeaponTypes').values(),
        *writer.sections['WeaponTypes'].values()]))
    waypoint = 19
    position = plan['map']['protected_building']['position']
    writer.put('Waypoints', waypoint, (position['y'] + 1) * 1000 + position['x'] + 1)
    return _action(42, registered.index(weapon), waypoint=_waypoint(waypoint)), armor, warhead, weapon


def _shield_activation(writer, plan, rules, warhead):
    """Charge a hidden self-targeted effect through Ares' complete warhead path.

    Native action 42 calls DamageArea directly, bypassing the projectile hook
    that applies Iron Curtain. GenericWarhead explicitly applies that effect.
    The Lab itself is the sole provider and target; no nearby unit is selected.
    """
    from .engine import _action

    owner, power = 'FFPLAYER', writer.key()
    writer.sections[power] = {
        'Name': 'Final Fortress emergency Lab shield', 'UIName': 'NOSTR:Emergency Lab shield',
        'Type': 'GenericWarhead', 'Action': 'None',
        # It cannot become ready naturally during this run. The health trigger
        # charges it once, and Shots=1 prevents any subsequent activation.
        'RechargeTime': f'{plan["survival_seconds"] / 60 + 1:g}',
        'IsPowered': 'no', 'ShowTimer': 'no', 'DisableableFromShell': 'no',
        'SW.RequiredHouses': owner, 'SW.AllowPlayer': 'yes', 'SW.AllowAI': 'no',
        'SW.InitialReady': 'no', 'SW.Shots': '1', 'SW.AutoFire': 'yes',
        'SW.ManualFire': 'no', 'SW.ShowCameo': 'no', 'SW.UseAITargeting': 'yes',
        'SW.AITargeting': 'Self', 'SW.AIRequiresTarget': 'none',
        'SW.AITargeting.Constraints': 'none', 'SW.AITargeting.Preference': 'none',
        'SW.Damage': '0', 'SW.Warhead': warhead, 'SW.CreateRadarEvent': 'no',
        'EVA.Ready': 'none', 'EVA.Activated': 'none', 'EVA.Detected': 'none',
        # "none" is a CSF label, not a way to disable text.
        'Message.Detected': 'NOSTR:', 'SW.Sound': 'none', 'SW.ActivationSound': 'none',
    }
    _register_map_type(writer.sections, writer.lines, rules, 'SuperWeaponTypes', power)
    registered = list(dict.fromkeys([
        *rules['SuperWeaponTypes'].values(),
        *section_value_map(writer.lines, 'SuperWeaponTypes').values(),
        *writer.sections['SuperWeaponTypes'].values()]))
    slot = next((field for field in ('SuperWeapon', 'SuperWeapon2')
                 if writer.sections['FFOBJECTIVE'].get(field, 'none').lower() in ('', 'none', '<none>')), None)
    if slot is None:
        raise ValueError('The Fortress Lab has no free slot for its emergency shield.')
    writer.put('FFOBJECTIVE', slot, power)
    index = registered.index(power)
    charge = _action(129, index, waypoint='100')
    charge[1] = '11'  # Native SuperWeapon argument type; P7 is charge percent.
    for field, value in dict(ShieldPower=power, ShieldIndex=index, ShieldOwner=owner,
                             ShieldSlot=slot).items():
        writer.put('FFLabSupport', field, value)
    return charge, owner


def apply_lab_support(writer, plan, rules, aliases, finished, loss_trigger):
    from .engine import _action, _waypoint
    from .messages import message_actions

    if plan.get('plan_version', 1) < 26:
        return
    effects = plan['effects']
    repair = effects['lab_emergency_repair']
    units = effects['lab_reserve_units']
    if not repair and not units:
        return

    # The tag on FFOBJECTIVE is already persistent. Add linked triggers rather
    # than replacing it: its original loss and ownership actions must survive.
    head = writer.sections['Triggers'][loss_trigger].split(',')
    linked = head[1]

    def attach(name, event, used, actions, *, owner='<none>'):
        nonlocal linked
        key, _ = writer.trigger(name,
            [(37, 0, finished), (37, 0, used), (event, 0, 0)], [])
        writer.put('Triggers', key, f'{owner},{linked},{name},0,1,1,1,0')
        actions = [_action(56, used), _action(54, trigger=key), *actions]
        writer.put('Actions', key, str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
        linked = key
        return key

    if repair:
        # Despite its editor label ("quarter health"), native Event 43 uses
        # ConditionRed. Keep Mental Omega's global 35% balance unchanged.
        red = section_value_map(writer.lines, 'AudioVisual').get(
            'conditionred', rules['AudioVisual']['ConditionRed'])
        fraction = float(red.rstrip('%')) / (100 if red.endswith('%') else 1)
        if abs(fraction - 0.35) > 1e-9:
            raise ValueError('Lab emergency repair requires the installed 35% red-health threshold.')
        used = writer.flag('Lab emergency repair used')
        strength = int(writer.sections['FFOBJECTIVE']['Strength'])
        blast, armor, warhead, weapon = _objective_blast(writer, plan, rules, -strength)
        trigger = attach('Lab emergency repair', 43, used,
            [blast, *message_actions('Emergency Lab repair used!')])
        for field, value in dict(Repair=trigger, RepairUsed=used, Armor=armor,
                                 Warhead=warhead, Weapon=weapon).items():
            writer.put('FFLabSupport', field, value)

    if units:
        used = writer.flag('Lab reserve squad used')
        actions = []
        shield_owner = '<none>'
        seconds = effects.get('lab_reserve_shield_seconds', 0)
        if plan.get('plan_version', 1) >= 27 and seconds:
            frames = seconds * 15
            _, armor, warhead, weapon = _objective_blast(writer, plan, rules, 0, extra_warhead={
                'IronCurtain.Duration': str(frames), 'IronCurtain.Cap': str(frames),
                'AllowZeroDamage': 'yes', 'EffectsRequireDamage': 'no', 'EffectsRequireVerses': 'yes',
                'Malicious': 'no',
            })
            writer.put('FFOBJECTIVE', 'IronCurtain.Modifier', 1)
            # The once flag is set before charging. Self targeting follows the
            # Lab even if emergency repair heals it during the same callback.
            # Negative healing bypasses native Iron Curtain damage immunity.
            activation, shield_owner = _shield_activation(writer, plan, rules, warhead)
            actions.append(activation)
            # Confirm the real activation, rather than claiming protection
            # merely because the health event requested it.
            activated, _ = writer.trigger('Lab shield activated',
                [(37, 0, finished), (36, 0, used), (75, 0, writer.sections['FFLabSupport']['ShieldIndex'])],
                message_actions(f'Lab shield active: {seconds}s'), owner=shield_owner)
            writer.put('FFLabSupport', 'ShieldActivated', activated)
            for field, value in dict(Armor=armor, ShieldWarhead=warhead, ShieldWeapon=weapon,
                                     ShieldFrames=frames).items():
                writer.put('FFLabSupport', field, value)
        deliveries = []
        for index, (actor, _, start) in enumerate(coalition(plan)):
            position = plan['map']['perk_layouts'][str(start)]['units']
            waypoint = 10 + index
            writer.put('Waypoints', waypoint, (position['y'] + 1) * 1000 + position['x'] + 2)
            # Separate native teams avoid partial placement of mixed forces.
            # This finite one-use grant does not wait for the periodic pool.
            for group, unit in enumerate(units, 1):
                team = writer.team(f'Fortress Lab reserve {actor} group {group}',
                    [{'type': aliases.get(unit['type'], unit['type']), 'count': unit['count']}],
                    start, attack=not human_actor(plan, actor), owner=actor)
                writer.put(team, 'Waypoint', _waypoint(waypoint))
                writer.put(team, 'VeteranLevel', effects.get('lab_reserve_veterancy', 0) + 1)
                writer.put(team, 'AreTeamMembersRecruitable', 'yes' if human_actor(plan, actor) else 'no')
                deliveries.append(writer.reinforce(team))
        if plan.get('plan_version', 1) >= 29:
            # Up to eighteen type/house teams exceed the native 511-byte
            # action limit. Deliver once through small, finish-guarded relays.
            following = None
            for offset in reversed(range(0, len(deliveries), 6)):
                batch = deliveries[offset:offset + 6]
                if following is not None:
                    batch = [*batch, _action(53, trigger=following)]
                following, _ = writer.trigger(f'Lab reserve deployment {offset // 6 + 1}',
                    [(37, 0, finished)], batch, disabled=True)
            writer.put('FFLabSupport', 'ReserveDeploy', following)
            actions.append(_action(53, trigger=following))
        else:
            actions.extend(deliveries)
        actions.extend(message_actions('Lab reserve squad deployed!'))
        if plan.get('plan_version', 1) >= 29:
            level = ('Rookie', 'Veteran', 'Elite')[effects.get('lab_reserve_veterancy', 0)]
            actions.extend(message_actions(f'{sum(u["count"] for u in units)} {level} units per base'))
        # A single hit can skip the half-health damage state entirely. Event
        # 43 is a fallback; both paths share a flag set before spawning units.
        fallback = attach('Lab reserve red-health fallback', 43, used, actions, owner=shield_owner)
        trigger = attach('Lab reserve squad', 42, used, actions, owner=shield_owner)
        for field, value in dict(Reserve=trigger, ReserveFallback=fallback, ReserveUsed=used).items():
            writer.put('FFLabSupport', field, value)
    head[1] = linked
    writer.put('Triggers', loss_trigger, ','.join(head))
