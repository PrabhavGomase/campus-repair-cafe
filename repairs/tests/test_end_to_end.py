from datetime import timedelta
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from repairs.models import (ItemCategory, PartDonation, PartUsage, RepairAssignment,
                            RepairFeedback, RepairRequest, RepairSession,
                            RepairStatusHistory, SparePart, User)


class CompleteBrowserFlowTests(TestCase):
    """Exercise the same form and page routes a user follows in the browser."""

    def setUp(self):
        self.category = ItemCategory.objects.create(name='Bicycle')
        self.coordinator = User.objects.create_user(
            username='coordinator_demo', password='StrongDemoPassword123!',
            role=User.Role.COORDINATOR)
        self.volunteer = User.objects.create_user(
            username='volunteer_demo', password='StrongDemoPassword123!',
            role=User.Role.VOLUNTEER)

    def login_as(self, username):
        self.client.post(reverse('logout'))
        response = self.client.post(reverse('login'), {
            'username': username, 'password': 'StrongDemoPassword123!'})
        self.assertEqual(response.status_code, 302)

    def test_full_repair_journey_and_reports(self):
        home = self.client.get('/')
        self.assertRedirects(home, '/accounts/login/?next=/')
        self.assertContains(self.client.get(reverse('login')), 'Log in')

        registration = self.client.post(reverse('register'), {
            'username': 'requester_demo', 'email': 'demo@example.test',
            'password1': 'StrongDemoPassword123!',
            'password2': 'StrongDemoPassword123!', 'role': 'coordinator'})
        self.assertRedirects(registration, reverse('dashboard'))
        requester = User.objects.get(username='requester_demo')
        self.assertEqual(requester.role, User.Role.REQUESTER)
        self.assertContains(self.client.get(reverse('dashboard')), 'Dashboard')

        created = self.client.post(reverse('request_create'), {
            'category': self.category.pk,
            'item_name': 'Desk lamp', 'description': 'Switch does not work'})
        repair = RepairRequest.objects.get(item_name='Desk lamp')
        self.assertRedirects(created, reverse('request_detail', args=[repair.pk]))
        self.assertContains(self.client.get(reverse('request_detail', args=[repair.pk])), 'Desk lamp')

        self.login_as('coordinator_demo')
        assignment = self.client.post(reverse('assign', args=[repair.pk]), {
            'volunteer': self.volunteer.pk, 'notes': 'Check wiring'})
        self.assertRedirects(assignment, reverse('request_detail', args=[repair.pk]))
        self.assertEqual(RepairAssignment.objects.get(request=repair).volunteer, self.volunteer)

        part_created = self.client.post(reverse('part_create'), {
            'name': 'Switch', 'unit': 'piece', 'reorder_level': 1})
        self.assertRedirects(part_created, reverse('part_list'))
        part = SparePart.objects.get(name='Switch')
        donated = self.client.post(reverse('donate'), {
            'part': part.pk, 'donor': requester.pk, 'quantity': 2,
            'notes': 'Unused spare switches'})
        self.assertRedirects(donated, reverse('part_list'))
        part.refresh_from_db()
        self.assertEqual(part.quantity, 2)
        self.assertEqual(PartDonation.objects.count(), 1)

        self.login_as('volunteer_demo')
        self.assertContains(self.client.get(reverse('request_detail', args=[repair.pk])), 'Desk lamp')
        started = timezone.localtime(timezone.now() - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M')
        session_response = self.client.post(reverse('add_session', args=[repair.pk]), {
            'started_at': started, 'findings': 'Broken switch', 'outcome': 'Replaced switch'})
        self.assertRedirects(session_response, reverse('request_detail', args=[repair.pk]))
        self.assertEqual(RepairSession.objects.filter(request=repair).count(), 1)

        used = self.client.post(reverse('use_part', args=[repair.pk]), {'part': part.pk, 'quantity': 1})
        self.assertRedirects(used, reverse('request_detail', args=[repair.pk]))
        part.refresh_from_db()
        self.assertEqual(part.quantity, 1)
        self.assertEqual(PartUsage.objects.get(request=repair).quantity, 1)
        self.assertContains(self.client.get(reverse('part_list')), 'Switch')

        completed = self.client.post(reverse('complete', args=[repair.pk]))
        self.assertRedirects(completed, reverse('request_detail', args=[repair.pk]))
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.COMPLETED)
        self.assertIsNotNone(repair.completed_at)
        self.assertEqual(RepairStatusHistory.objects.filter(request=repair).count(), 3)

        self.login_as('requester_demo')
        feedback = self.client.post(reverse('feedback', args=[repair.pk]), {
            'rating': 5, 'comment': 'Lamp works again'})
        self.assertRedirects(feedback, reverse('request_detail', args=[repair.pk]))
        self.assertEqual(RepairFeedback.objects.get(request=repair).rating, 5)

        self.login_as('coordinator_demo')
        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, 'Completed')
        self.assertEqual(dashboard.context['counts']['completed'], 1)
        report = self.client.get(reverse('reports'))
        self.assertContains(report, 'Requests by category')
        self.assertContains(report, 'Bicycle')
        self.assertContains(report, 'Switch')
        self.assertEqual(report.context['completed'], 1)
        self.assertEqual(report.context['donated'], 2)
        with connection.cursor() as cursor:
            cursor.execute('SELECT status, parts_used FROM repair_summary WHERE id = %s', [repair.pk])
            self.assertEqual(cursor.fetchone(), ('completed', 1))

    def test_search_filter_pagination_and_database_constraints(self):
        self.login_as('coordinator_demo')
        for index in range(12):
            RepairRequest.objects.create(requester=self.coordinator, category=self.category,
                                         item_name=f'Lamp {index}', description='Test item')
        first_page = self.client.get(reverse('request_list'), {'q': 'Lamp', 'status': 'new'})
        self.assertEqual(first_page.context['page'].paginator.count, 12)
        self.assertEqual(len(first_page.context['page'].object_list), 10)
        second_page = self.client.get(reverse('request_list'), {'q': 'Lamp', 'status': 'new', 'page': 2})
        self.assertEqual(len(second_page.context['page'].object_list), 2)

        part = SparePart.objects.create(name='Wire', quantity=0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PartDonation.objects.create(part=part, donor=self.coordinator, quantity=0)
