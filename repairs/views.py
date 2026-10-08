from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import AssignmentForm, DonationForm, FeedbackForm, PartForm, RegisterForm, RequestForm, SessionForm, UsageForm
from .models import PartUsage, RepairRequest, SparePart, User
from .services import change_status, complete_repair, record_donation, record_usage


def is_coordinator(user):
    return user.is_superuser or user.role == User.Role.COORDINATOR


def assigned_to(user, repair):
    return repair.assignment.volunteer_id == user.pk if hasattr(repair, 'assignment') else False


def visible_requests(user):
    qs = RepairRequest.objects.select_related('requester', 'category', 'assignment__volunteer')
    if is_coordinator(user):
        return qs
    if user.role == User.Role.VOLUNTEER:
        return qs.filter(assignment__volunteer=user)
    return qs.filter(requester=user)


def get_visible_request(user, pk):
    return get_object_or_404(visible_requests(user), pk=pk)


def coordinator_required(view):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_coordinator(request.user):
            return HttpResponseForbidden('Coordinator access required.')
        return view(request, *args, **kwargs)
    return wrapper


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    qs = visible_requests(request.user)
    counts = {key: qs.filter(status=key).count() for key, _ in RepairRequest.Status.choices}
    return render(request, 'repairs/dashboard.html', {
        'counts': counts, 'total': qs.count(), 'recent': qs[:8],
        'parts_low': SparePart.objects.filter(quantity__lte=F('reorder_level'))[:5] if is_coordinator(request.user) else [],
    })


@login_required
def request_list(request):
    qs = visible_requests(request.user)
    query = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', '')
    if query:
        qs = qs.filter(Q(item_name__icontains=query) | Q(description__icontains=query))
    if status in RepairRequest.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 10).get_page(request.GET.get('page'))
    return render(request, 'repairs/request_list.html', {'page': page, 'query': query, 'status': status,
                  'statuses': RepairRequest.Status.choices})


@login_required
def request_create(request):
    form = RequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        repair = form.save(commit=False)
        repair.requester = request.user
        repair.save()
        messages.success(request, 'Repair request submitted.')
        return redirect('request_detail', pk=repair.pk)
    return render(request, 'repairs/form.html', {'form': form, 'title': 'New repair request'})


@login_required
def request_detail(request, pk):
    repair = get_visible_request(request.user, pk)
    return render(request, 'repairs/request_detail.html', {
        'repair': repair, 'coordinator': is_coordinator(request.user),
        'assigned': assigned_to(request.user, repair),
    })


@login_required
def request_edit(request, pk):
    repair = get_visible_request(request.user, pk)
    if repair.requester_id != request.user.pk or repair.status != RepairRequest.Status.NEW:
        return HttpResponseForbidden('Only the requester can edit a new request.')
    form = RequestForm(request.POST or None, instance=repair)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('request_detail', pk=pk)
    return render(request, 'repairs/form.html', {'form': form, 'title': 'Edit request'})


@coordinator_required
def assign(request, pk):
    repair = get_object_or_404(RepairRequest, pk=pk)
    if repair.status in (RepairRequest.Status.COMPLETED, RepairRequest.Status.CANCELLED):
        return HttpResponseForbidden('Closed requests cannot be assigned.')
    existing = getattr(repair, 'assignment', None)
    form = AssignmentForm(request.POST or None, instance=existing)
    if request.method == 'POST' and form.is_valid():
        assignment = form.save(commit=False)
        assignment.request = repair
        assignment.assigned_by = request.user
        assignment.save()
        change_status(repair, RepairRequest.Status.ASSIGNED, request.user)
        messages.success(request, 'Volunteer assigned.')
        return redirect('request_detail', pk=pk)
    return render(request, 'repairs/form.html', {'form': form, 'title': 'Assign volunteer'})


@login_required
def add_session(request, pk):
    repair = get_visible_request(request.user, pk)
    if not (is_coordinator(request.user) or assigned_to(request.user, repair)):
        return HttpResponseForbidden('Volunteer access required.')
    if repair.status in (RepairRequest.Status.COMPLETED, RepairRequest.Status.CANCELLED):
        return HttpResponseForbidden('This repair is closed.')
    form = SessionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        session = form.save(commit=False)
        session.request = repair
        session.volunteer = repair.assignment.volunteer if hasattr(repair, 'assignment') else request.user
        session.save()
        change_status(repair, RepairRequest.Status.IN_PROGRESS, request.user)
        return redirect('request_detail', pk=pk)
    return render(request, 'repairs/form.html', {'form': form, 'title': 'Record repair session'})


@login_required
def use_part(request, pk):
    repair = get_visible_request(request.user, pk)
    if not (is_coordinator(request.user) or assigned_to(request.user, repair)):
        return HttpResponseForbidden('Volunteer access required.')
    form = UsageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            record_usage(repair=repair, part=form.cleaned_data['part'],
                         quantity=form.cleaned_data['quantity'], actor=request.user)
            messages.success(request, 'Part usage recorded.')
            return redirect('request_detail', pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, 'repairs/form.html', {'form': form, 'title': 'Use a spare part'})


@login_required
@require_POST
def complete(request, pk):
    repair = get_visible_request(request.user, pk)
    if not (is_coordinator(request.user) or assigned_to(request.user, repair)):
        return HttpResponseForbidden('Volunteer access required.')
    try:
        complete_repair(repair, request.user)
        messages.success(request, 'Repair completed.')
    except ValidationError as error:
        messages.error(request, '; '.join(error.messages))
    return redirect('request_detail', pk=pk)


@login_required
@require_POST
def cancel(request, pk):
    repair = get_visible_request(request.user, pk)
    if not (is_coordinator(request.user) or repair.requester_id == request.user.pk):
        return HttpResponseForbidden('No permission to cancel.')
    if repair.status not in (RepairRequest.Status.NEW, RepairRequest.Status.ASSIGNED):
        return HttpResponseForbidden('This request cannot be cancelled now.')
    change_status(repair, RepairRequest.Status.CANCELLED, request.user)
    return redirect('request_detail', pk=pk)


@login_required
def part_list(request):
    query = request.GET.get('q', '').strip()[:100]
    qs = SparePart.objects.all().order_by('name')
    if query:
        qs = qs.filter(name__icontains=query)
    return render(request, 'repairs/part_list.html', {'page': Paginator(qs, 10).get_page(request.GET.get('page')),
                  'query': query, 'coordinator': is_coordinator(request.user)})


@coordinator_required
def part_create(request):
    form = PartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('part_list')
    return render(request, 'repairs/form.html', {'form': form, 'title': 'Add spare part'})


@coordinator_required
def donate(request):
    form = DonationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        record_donation(**form.cleaned_data)
        messages.success(request, 'Donation recorded and stock updated.')
        return redirect('part_list')
    return render(request, 'repairs/form.html', {'form': form, 'title': 'Record donation'})


@coordinator_required
def reports(request):
    by_category = RepairRequest.objects.values('category__name').annotate(total=Count('id')).order_by('-total')
    top_parts = PartUsage.objects.values('part__name').annotate(total=Sum('quantity')).order_by('-total')[:10]
    return render(request, 'repairs/reports.html', {'by_category': by_category, 'top_parts': top_parts,
                  'completed': RepairRequest.objects.filter(status=RepairRequest.Status.COMPLETED).count(),
                  'donated': SparePart.objects.aggregate(total=Sum('donations__quantity'))['total'] or 0})


@login_required
def request_api(request, pk):
    repair = get_visible_request(request.user, pk)
    return JsonResponse({'id': repair.pk, 'item': repair.item_name, 'status': repair.status,
                         'category': repair.category.name, 'created_at': repair.created_at.isoformat()})


@login_required
def feedback(request, pk):
    repair = get_visible_request(request.user, pk)
    if repair.requester_id != request.user.pk or repair.status != RepairRequest.Status.COMPLETED:
        return HttpResponseForbidden('Feedback is available to the requester after completion.')
    if hasattr(repair, 'feedback'):
        return HttpResponseForbidden('Feedback has already been submitted.')
    form = FeedbackForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.request = repair
        item.save()
        return redirect('request_detail', pk=pk)
    return render(request, 'repairs/form.html', {'form': form, 'title': 'Rate the repair'})
