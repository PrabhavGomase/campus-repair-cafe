from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    class Role(models.TextChoices):
        REQUESTER = "requester", "Requester"
        VOLUNTEER = "volunteer", "Volunteer"
        COORDINATOR = "coordinator", "Coordinator"
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.REQUESTER)
    phone = models.CharField(max_length=20, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(models.functions.Lower('email'),
                                            condition=~Q(email=''), name='unique_nonempty_email_ci')]


class ItemCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    def __str__(self): return self.name


class RepairRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_PARTS = "waiting_parts", "Waiting for parts"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
    requester = models.ForeignKey(User, on_delete=models.PROTECT, related_name="requests")
    category = models.ForeignKey(ItemCategory, on_delete=models.PROTECT)
    item_name = models.CharField(max_length=120)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"], name="request_status_date_idx")]
    def __str__(self): return f"#{self.pk} {self.item_name}"


class RepairAssignment(models.Model):
    request = models.OneToOneField(RepairRequest, on_delete=models.CASCADE, related_name="assignment")
    volunteer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assigned_requests")
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)


class RepairSession(models.Model):
    request = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name="sessions")
    volunteer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sessions")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    findings = models.TextField()
    outcome = models.TextField(blank=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gte=models.F("started_at")), name="session_end_after_start")]


class SparePart(models.Model):
    name = models.CharField(max_length=120, unique=True)
    unit = models.CharField(max_length=30, default="piece")
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=0), name="part_quantity_nonnegative")]
    def __str__(self): return self.name


class PartDonation(models.Model):
    part = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name="donations")
    donor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="donations")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    donated_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="donation_positive")]


class PartUsage(models.Model):
    request = models.ForeignKey(RepairRequest, on_delete=models.PROTECT, related_name="parts_used")
    part = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name="usages")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    used_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="usage_positive")]


class RepairStatusHistory(models.Model):
    request = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name="history")
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    class Meta:
        ordering = ["-changed_at"]


class RepairFeedback(models.Model):
    request = models.OneToOneField(RepairRequest, on_delete=models.CASCADE, related_name="feedback")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name="rating_1_to_5")]
