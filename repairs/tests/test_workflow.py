from datetime import timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from repairs.models import (ItemCategory, RepairAssignment, RepairRequest, RepairSession,
                            RepairStatusHistory, SparePart, User)
from repairs.services import change_status, complete_repair, record_donation, record_usage


class RepairWorkflowTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(username='student', password='LongExamplePass123!', role='requester')
        self.other = User.objects.create_user(username='other', password='LongExamplePass123!', role='requester')
        self.volunteer = User.objects.create_user(username='helper', password='LongExamplePass123!', role='volunteer')
        self.coordinator = User.objects.create_user(username='manager', password='LongExamplePass123!', role='coordinator')
        self.category = ItemCategory.objects.create(name='Bicycles')
        self.repair = RepairRequest.objects.create(requester=self.requester, category=self.category,
                                                   item_name='Bicycle light', description='Does not switch on')
        self.part = SparePart.objects.create(name='Battery', quantity=0)

    def test_requester_cannot_assign_or_see_other_request(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('request_detail', args=[self.repair.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('request_api', args=[self.repair.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('assign', args=[self.repair.pk]),
                                          {'volunteer': self.volunteer.pk}).status_code, 403)

    def test_registration_cannot_choose_privileged_role(self):
        response = self.client.post(reverse('register'), {'username': 'newuser', 'email': 'new@example.com',
            'password1': 'LongExamplePass123!', 'password2': 'LongExamplePass123!', 'role': 'coordinator'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(username='newuser').role, User.Role.REQUESTER)

    def test_donation_and_usage_are_atomic(self):
        record_donation(part=self.part, donor=self.requester, quantity=3)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)
        record_usage(repair=self.repair, part=self.part, quantity=2, actor=self.volunteer)
        with self.assertRaises(ValidationError):
            record_usage(repair=self.repair, part=self.part, quantity=2, actor=self.volunteer)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 1)
        self.assertEqual(self.repair.parts_used.count(), 1)

    def test_assignment_session_completion_and_history(self):
        RepairAssignment.objects.create(request=self.repair, volunteer=self.volunteer, assigned_by=self.coordinator)
        change_status(self.repair, RepairRequest.Status.ASSIGNED, self.coordinator)
        with self.assertRaises(ValidationError):
            complete_repair(self.repair, self.volunteer)
        RepairSession.objects.create(request=self.repair, volunteer=self.volunteer,
                                     started_at=timezone.now() - timedelta(hours=1), findings='Loose wire')
        complete_repair(self.repair, self.volunteer)
        self.repair.refresh_from_db()
        self.assertEqual(self.repair.status, RepairRequest.Status.COMPLETED)
        self.assertIsNotNone(self.repair.completed_at)
        self.assertEqual(RepairStatusHistory.objects.filter(request=self.repair).count(), 2)

    def test_volunteer_sees_only_assigned_requests(self):
        self.client.force_login(self.volunteer)
        self.assertEqual(self.client.get(reverse('request_detail', args=[self.repair.pk])).status_code, 404)
        RepairAssignment.objects.create(request=self.repair, volunteer=self.volunteer, assigned_by=self.coordinator)
        self.assertEqual(self.client.get(reverse('request_detail', args=[self.repair.pk])).status_code, 200)

    def test_usage_rejected_when_repair_closed_after_object_was_loaded(self):
        record_donation(part=self.part, donor=self.requester, quantity=3)
        # Simulate another request completing the repair after this object was loaded.
        RepairRequest.objects.filter(pk=self.repair.pk).update(status=RepairRequest.Status.COMPLETED)
        self.assertNotEqual(self.repair.status, RepairRequest.Status.COMPLETED)  # stale copy
        with self.assertRaises(ValidationError):
            record_usage(repair=self.repair, part=self.part, quantity=1, actor=self.volunteer)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)
        self.assertEqual(self.repair.parts_used.count(), 0)
