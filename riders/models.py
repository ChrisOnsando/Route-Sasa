from django.db import models
from django.contrib.auth.models import User

class Rider(models.Model):
    """Delivery riders"""
    VEHICLE_TYPES = [
        ('MOTORCYCLE', 'Motorcycle'),
        ('BICYCLE', 'Bicycle'),
        ('VAN', 'Van'),
        ('PICKUP', 'Pickup Truck'),
    ]
    
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('ON_DELIVERY', 'On Delivery'),
        ('OFFLINE', 'Offline'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, unique=True)
    
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default='MOTORCYCLE')
    vehicle_registration = models.CharField(max_length=50, blank=True)
    
    preferred_landmarks = models.ManyToManyField('orders.Landmark', blank=True, related_name='preferred_riders')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    current_location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    total_deliveries = models.IntegerField(default=0)
    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.vehicle_type}"
    
    @property
    def success_rate(self):
        if self.total_deliveries == 0:
            return 0
        return (self.successful_deliveries / self.total_deliveries) * 100
    
    class Meta:
        ordering = ['-rating', '-successful_deliveries']
