from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from .models import PartDonation, PartUsage, RepairRequest, RepairStatusHistory, SparePart


@transaction.atomic
def change_status(repair, status, actor=None, note=''):
    if repair.status == status:
        return
    previous = repair.status
    repair.status = status
    if connection.vendor == 'postgresql' and actor:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('repaircafe.actor_id', %s, true)", [str(actor.pk)])
    repair.save(update_fields=['status', 'updated_at'])
    # PostgreSQL has a database trigger; SQLite uses the same history model here.
    if connection.vendor != 'postgresql':
        RepairStatusHistory.objects.create(request=repair, old_status=previous,
                                           new_status=status, changed_by=actor, note=note)


@transaction.atomic
def record_donation(*, part, donor, quantity, notes=''):
    if quantity < 1:
        raise ValidationError('Quantity must be positive.')
    donation = PartDonation.objects.create(part=part, donor=donor, quantity=quantity, notes=notes)
    SparePart.objects.filter(pk=part.pk).update(quantity=F('quantity') + quantity)
    return donation


@transaction.atomic
def record_usage(*, repair, part, quantity, actor):
    if quantity < 1:
        raise ValidationError('Quantity must be positive.')
    # Lock the repair row and re-check its status, so a repair that was
    # completed or cancelled in the meantime cannot consume stock.
    repair = RepairRequest.objects.select_for_update().get(pk=repair.pk)
    if repair.status in {RepairRequest.Status.COMPLETED, RepairRequest.Status.CANCELLED}:
        raise ValidationError('This repair is closed.')
    updated = SparePart.objects.filter(pk=part.pk, quantity__gte=quantity).update(quantity=F('quantity') - quantity)
    if not updated:
        raise ValidationError('Not enough parts in stock.')
    return PartUsage.objects.create(request=repair, part=part, quantity=quantity, recorded_by=actor)


@transaction.atomic
def complete_repair(repair, actor):
    repair = RepairRequest.objects.select_for_update().get(pk=repair.pk)
    if repair.status in {RepairRequest.Status.COMPLETED, RepairRequest.Status.CANCELLED}:
        raise ValidationError('This repair is already closed.')
    if not repair.sessions.exists():
        raise ValidationError('Record a repair session before completing this request.')
    if connection.vendor == 'postgresql':
        # A stored procedure is used only for this advanced database operation.
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('repaircafe.actor_id', %s, true)", [str(actor.pk)])
            cursor.execute('CALL complete_repair(%s)', [repair.pk])
    else:
        change_status(repair, RepairRequest.Status.COMPLETED, actor)
        repair.completed_at = timezone.now()
        repair.save(update_fields=['completed_at', 'updated_at'])
