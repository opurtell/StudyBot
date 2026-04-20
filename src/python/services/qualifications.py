from services.registry import Service


def _closure(base_id: str, service: Service) -> frozenset[str]:
    """Compute the transitive closure of a base qualification following implications."""
    seen = {base_id}
    stack = [base_id]
    bases_by_id = {b.id: b for b in service.qualifications.bases}
    while stack:
        cur = stack.pop()
        for implied in bases_by_id[cur].implies:
            if implied not in bases_by_id:
                raise ValueError(
                    f"Base {cur!r} implies unknown qualification {implied!r} in service {service.id}"
                )
            if implied not in seen:
                seen.add(implied)
                stack.append(implied)
    return frozenset(seen)


def effective_qualifications(
    base_id: str,
    endorsement_ids: tuple[str, ...],
    service: Service,
) -> frozenset[str]:
    """
    Compute effective qualifications: transitive closure of base plus valid endorsements.

    Args:
        base_id: The base qualification ID (e.g. "AP", "ICP", "PARAMEDIC", "VAO")
        endorsement_ids: Tuple of endorsement IDs (e.g. ("ICP",) for AT paramedics)
        service: The service containing qualification definitions

    Returns:
        Frozenset of all effective qualification IDs

    Raises:
        ValueError: If base_id or any endorsement_id is unknown, or if an endorsement
                    requires a base qualification that the user does not have
    """
    bases_by_id = {b.id: b for b in service.qualifications.bases}
    endorsements_by_id = {e.id: e for e in service.qualifications.endorsements}

    if base_id not in bases_by_id:
        raise ValueError(f"Unknown base {base_id} for service {service.id}")

    for eid in endorsement_ids:
        if eid not in endorsements_by_id:
            raise ValueError(f"Unknown endorsement {eid} for service {service.id}")
        endorsement = endorsements_by_id[eid]
        if endorsement.requires_base and base_id not in endorsement.requires_base:
            raise ValueError(
                f"Endorsement {eid} requires base one of {endorsement.requires_base}, got {base_id}"
            )

    return _closure(base_id, service) | frozenset(endorsement_ids)


def is_in_scope(required: frozenset[str], effective: frozenset[str]) -> bool:
    """
    Check whether a set of required qualifications is satisfied by effective qualifications.

    Args:
        required: Frozenset of required qualification IDs
        effective: Frozenset of user's effective qualification IDs

    Returns:
        True if required is a subset of effective, False otherwise
    """
    return required.issubset(effective)
