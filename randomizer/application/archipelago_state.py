"""Small persisted-state helpers for staged and active AP runs."""


def normalize_archipelago_activation(state):
    """Migrate pre-staging AP state without downgrading a real AP session."""
    if not isinstance(state, dict):
        return False
    ap_state = state.get('archipelago')
    if (
        not isinstance(ap_state, dict)
        or not ap_state.get('manifest_checksum')
        or not isinstance(ap_state.get('run_manifest'), dict)
    ):
        return False

    activation = str(ap_state.get('activation') or '').strip().lower()
    if activation not in {'staged', 'active'}:
        validated_session_evidence = bool(
            ap_state.get('slot_data')
            or ap_state.get('received_rewards')
            or ap_state.get('checkpoint')
        )
        activation = (
            'active'
            if ap_state.get('enabled') and validated_session_evidence
            else 'staged'
        )

    enabled = activation == 'active'
    changed = (
        ap_state.get('activation') != activation
        or bool(ap_state.get('enabled')) != enabled
    )
    ap_state['activation'] = activation
    ap_state['enabled'] = enabled
    return changed
