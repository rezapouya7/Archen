"""Job-related domain services."""

from __future__ import annotations

from typing import List, Tuple

from django.db import transaction

from production_line.models import ProductionLog


def _collect_log_history(job) -> List[Tuple[ProductionLog, str | None]]:
    """Return ordered log rows with their previous section slug."""
    logs = list(
        job.productionlog_set.select_related('job', 'product', 'part')
        .order_by('logged_at', 'id')
    )
    contexts: List[Tuple[ProductionLog, str | None]] = []
    prev_section: str | None = None
    for log in logs:
        contexts.append((log, prev_section))
        prev_section = (str(log.section or '').strip().lower()) or None
    return contexts


def delete_job_completely(job) -> tuple[int, int]:
    """Remove a job together with its logs and revert inventory.

    Returns a tuple ``(logs_deleted, job_deleted)`` where ``job_deleted`` is 1 on
    success so that callers can aggregate counters.
    """
    with transaction.atomic():
        contexts = _collect_log_history(job)
        for log, prev_section in reversed(contexts):
            log.rollback_inventory(prev_section)
            log.delete()
        job.delete()
    return (len(contexts), 1)


def rewind_job_progress(job, ordered_flow: list[str], target_cursor: int, current_cursor: int) -> tuple[int, str | None]:
    """Rollback logs so that the job's next allowed section index becomes ``target_cursor``.

    ``ordered_flow`` must contain the allowed sections in process order.
    ``current_cursor`` represents the current contiguous completion count (i.e. the
    index of the highlighted/next section).  The function removes logs for the
    slice ``ordered_flow[target_cursor:current_cursor]`` (if any) while restoring
    inventory via ``ProductionLog.rollback_inventory``.

    Returns a tuple ``(removed_logs, new_current_section_slug)``.  The caller is
    responsible for persisting the updated ``current_section`` on the job.
    """

    if not ordered_flow:
        return (0, getattr(job, 'current_section', None))

    target_cursor = max(0, min(target_cursor, len(ordered_flow)))
    current_cursor = max(target_cursor, min(current_cursor, len(ordered_flow)))

    slice_slugs = ordered_flow[target_cursor:current_cursor]
    if not slice_slugs:
        new_current = ordered_flow[target_cursor - 1] if target_cursor > 0 else None
        return (0, new_current)

    slice_set = set(slice_slugs)
    removed = 0

    with transaction.atomic():
        contexts = _collect_log_history(job)
        for log, prev_section in reversed(contexts):
            slug = str(getattr(log, 'section', '') or '').lower()
            if slug in slice_set:
                log.rollback_inventory(prev_section)
                log.delete()
                removed += 1
                slice_set.remove(slug)
                if not slice_set:
                    break

    new_current = ordered_flow[target_cursor - 1] if target_cursor > 0 else None
    return (removed, new_current)
