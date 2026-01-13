from django.contrib import admin
from django.utils.html import format_html
from .models import Rider

@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = [
        'get_full_name', 'phone_number', 'vehicle_type',
        'status_badge', 'rating', 'success_rate_display',
        'total_deliveries', 'last_active'
    ]
    list_filter = ['status', 'vehicle_type', 'created_at']
    search_fields = [
        'user__first_name', 'user__last_name',
        'phone_number', 'vehicle_registration'
    ]
    filter_horizontal = ['preferred_landmarks']
    readonly_fields = [
        'total_deliveries', 'successful_deliveries', 'failed_deliveries',
        'created_at', 'updated_at', 'last_active'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'phone_number')
        }),
        ('Vehicle Details', {
            'fields': ('vehicle_type', 'vehicle_registration')
        }),
        ('Operational Areas', {
            'fields': ('preferred_landmarks',)
        }),
        ('Current Status', {
            'fields': ('status', 'current_location_lat', 'current_location_lng')
        }),
        ('Performance Metrics', {
            'fields': (
                'total_deliveries', 'successful_deliveries',
                'failed_deliveries', 'rating'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_active'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Name'
    
    def status_badge(self, obj):
        colors = {
            'AVAILABLE': '#28a745',
            'ON_DELIVERY': '#007bff',
            'OFFLINE': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def success_rate_display(self, obj):
        rate = obj.success_rate
        color = '#28a745' if rate >= 90 else '#ffa500' if rate >= 75 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    actions = ['mark_available', 'mark_offline']
    
    def mark_available(self, request, queryset):
        updated = queryset.update(status='AVAILABLE')
        self.message_user(request, f'{updated} riders marked as available.')
    mark_available.short_description = 'Mark as available'
    
    def mark_offline(self, request, queryset):
        updated = queryset.update(status='OFFLINE')
        self.message_user(request, f'{updated} riders marked as offline.')
    mark_offline.short_description = 'Mark as offline'
