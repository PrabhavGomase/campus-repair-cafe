from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('requests/', views.request_list, name='request_list'),
    path('requests/new/', views.request_create, name='request_create'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('requests/<int:pk>/edit/', views.request_edit, name='request_edit'),
    path('requests/<int:pk>/assign/', views.assign, name='assign'),
    path('requests/<int:pk>/session/', views.add_session, name='add_session'),
    path('requests/<int:pk>/use-part/', views.use_part, name='use_part'),
    path('requests/<int:pk>/complete/', views.complete, name='complete'),
    path('requests/<int:pk>/cancel/', views.cancel, name='cancel'),
    path('requests/<int:pk>/feedback/', views.feedback, name='feedback'),
    path('parts/', views.part_list, name='part_list'),
    path('parts/new/', views.part_create, name='part_create'),
    path('donations/new/', views.donate, name='donate'),
    path('reports/', views.reports, name='reports'),
    path('api/requests/<int:pk>/', views.request_api, name='request_api'),
]
