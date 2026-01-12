from django.contrib import admin
from django.utils.html import format_html
from .models import Landmark, Order, SMSLog, DeliveryRoute


@admin.register(Landmark)
class LandmarkAdmin(admin.ModelAdmin):
    list_display = ['name', 'area', 'city', 'created_at']
    list_filter = ['city', 'area']
    search_fields = ['name', 'area', 'description']
    ordering = ['area', 'name']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'customer_name', 'landmark', 
        'status_badge', 'delivery_date', 'assigned_rider',
        'created_at'
    ]
    list_filter = ['status', 'delivery_date', 'created_at']
    search_fields = ['order_number', 'customer_name', 'customer_phone']
    readonly_fields = [
        'order_number', 'created_at', 'updated_at',
        'confirmation_sms_sent_at', 'customer_confirmed_at', 'delivered_at'
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'vendor', 'status', 'items_description')
        }),
        ('Customer Details', {
            'fields': ('customer_name', 'customer_phone')
        }),
        ('Delivery Location', {
            'fields': ('landmark', 'additional_directions')
        }),
        ('Delivery Schedule', {
            'fields': ('delivery_date', 'delivery_time_start', 'delivery_time_end')
        }),
        ('Assignment', {
            'fields': ('assigned_rider',)
        }),
        ('SMS Tracking', {
            'fields': (
                'confirmation_sms_sent', 'confirmation_sms_sent_at', 
                'customer_confirmed_at'
            )
        }),
        ('Delivery Status', {
            'fields': ('delivered_at', 'delivery_proof', 'failure_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'PENDING_CONFIRMATION': '#ffa500',
            'CONFIRMED': '#28a745',
            'RESCHEDULE_REQUESTED': '#ff6b6b',
            'ASSIGNED': '#007bff',
            'IN_TRANSIT': '#17a2b8',
            'DELIVERED': '#28a745',
            'FAILED': '#dc3545',
            'CANCELLED': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['send_confirmation_sms', 'mark_as_delivered']
    
    def send_confirmation_sms(self, request, queryset):
        from .sms_service import sms_service
        count = 0
        for order in queryset:
            if order.status == 'PENDING_CONFIRMATION':
                if sms_service.send_order_confirmation_sms(order):
                    count += 1
        self.message_user(request, f'{count} confirmation SMS sent successfully.')
    send_confirmation_sms.short_description = 'Send confirmation SMS'
    
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='DELIVERED', delivered_at=timezone.now())
        self.message_user(request, f'{updated} orders marked as delivered.')
    mark_as_delivered.short_description = 'Mark as delivered'


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'message_type', 'recipient_phone',
        'delivered_badge', 'response_received', 'sent_at'
    ]
    list_filter = ['message_type', 'delivered', 'response_received', 'sent_at']
    search_fields = ['order__order_number', 'recipient_phone', 'message_content']
    readonly_fields = ['sent_at', 'response_at']
    
    def delivered_badge(self, obj):
        if obj.delivered:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Delivered</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Failed</span>'
        )
    delivered_badge.short_description = 'Delivery Status'


@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'rider', 'landmark', 'route_date',
        'sequence', 'estimated_arrival', 'completed', 'order_count'
    ]
    list_filter = ['route_date', 'completed', 'rider']
    search_fields = ['rider__user__first_name', 'rider__user__last_name', 'landmark__name']
    filter_horizontal = ['orders']
    
    def order_count(self, obj):
        return obj.orders.count()
    order_count.short_description = 'Orders'
