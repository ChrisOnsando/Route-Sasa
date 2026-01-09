from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Landmark(models.Model):
    """Popular landmarks for delivery reference"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    area = models.CharField(max_length=100)
    city = models.CharField(max_length=100, default='Nairobi')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.area}"
    
    class Meta:
        ordering = ['area', 'name']


class Order(models.Model):
    ORDER_STATUS = [
        ('PENDING_CONFIRMATION', 'Pending Customer Confirmation'),
        ('CONFIRMED', 'Confirmed by Customer'),
        ('RESCHEDULE_REQUESTED', 'Reschedule Requested'),
        ('ASSIGNED', 'Assigned to Rider'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered Successfully'),
        ('FAILED', 'Delivery Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendor_orders')
    
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    
    landmark = models.ForeignKey(Landmark, on_delete=models.SET_NULL, null=True)
    additional_directions = models.TextField(help_text="Extra directions from landmark")
    
    delivery_date = models.DateField()
    delivery_time_start = models.TimeField()
    delivery_time_end = models.TimeField()
    
    items_description = models.TextField(help_text="Description of items to deliver")
    
    status = models.CharField(max_length=30, choices=ORDER_STATUS, default='PENDING_CONFIRMATION')
    assigned_rider = models.ForeignKey('riders.Rider', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_orders')
    
    confirmation_sms_sent = models.BooleanField(default=False)
    confirmation_sms_sent_at = models.DateTimeField(null=True, blank=True)
    customer_confirmed_at = models.DateTimeField(null=True, blank=True)
    
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_proof = models.TextField(blank=True, help_text="Delivery notes or proof")
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            import random
            self.order_number = f"ORD{timezone.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.order_number} - {self.customer_name} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']


class SMSLog(models.Model):
    """Track all SMS communications"""
    SMS_TYPES = [
        ('CONFIRMATION', 'Order Confirmation Request'),
        ('RIDER_ASSIGNMENT', 'Rider Assignment Notification'),
        ('DELIVERY_SUCCESS', 'Delivery Success Notification'),
        ('DELIVERY_FAILED', 'Delivery Failed Notification'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='sms_logs')
    recipient_phone = models.CharField(max_length=20)
    message_type = models.CharField(max_length=30, choices=SMS_TYPES)
    message_content = models.TextField()
    
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered = models.BooleanField(default=False)
    delivery_status = models.CharField(max_length=50, blank=True)
    
    response_received = models.BooleanField(default=False)
    response_content = models.CharField(max_length=10, blank=True)
    response_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.message_type} to {self.recipient_phone} - {self.order.order_number}"
    
    class Meta:
        ordering = ['-sent_at']


class DeliveryRoute(models.Model):
    """Optimized delivery routes for riders"""
    rider = models.ForeignKey('riders.Rider', on_delete=models.CASCADE, related_name='routes')
    route_date = models.DateField()
    landmark = models.ForeignKey(Landmark, on_delete=models.CASCADE)
    
    orders = models.ManyToManyField(Order, related_name='routes')
    
    sequence = models.IntegerField(default=0, help_text="Order of this stop in the route")
    estimated_arrival = models.TimeField()
    
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Route {self.id} - {self.rider.user.get_full_name()} - {self.landmark.name}"
    
    class Meta:
        ordering = ['route_date', 'sequence']
