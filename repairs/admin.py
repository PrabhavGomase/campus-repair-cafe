from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ItemCategory, SparePart

@admin.register(User)
class RepairUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Repair Café', {'fields': ('role', 'phone')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Repair Café', {'fields': ('role', 'email')}),)
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role', 'is_staff')

admin.site.register(ItemCategory)

@admin.register(SparePart)
class SparePartAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'unit', 'reorder_level')
    readonly_fields = ('quantity',)
