from rest_framework import serializers
from .models import Landmark, Order, SMSLog, DeliveryRoute
from riders.models import Rider
from django.contrib.auth.models import User


class LandmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Landmark
        fields = [
            'id', 'name', 'description', 'area', 'city',
            'latitude', 'longitude', 'created_at'
        ]
        read_only_fields = ['created_at']


class RiderSimpleSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Rider
        fields = [
            'id', 'full_name', 'phone_number', 'vehicle_type',
            'status', 'rating', 'success_rate'
        ]


class OrderSerializer(serializers.ModelSerializer):
    landmark_name = serializers.CharField(source='landmark.name', read_only=True)
    assigned_rider_name = serializers.CharField(
        source='assigned_rider.user.get_full_name',
        read_only=True,
        allow_null=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer_name', 'customer_phone',
            'landmark', 'landmark_name', 'additional_directions',
            'delivery_date', 'delivery_time_start', 'delivery_time_end',
            'items_description', 'status', 'status_display',
            'assigned_rider', 'assigned_rider_name',
            'confirmation_sms_sent', 'delivered_at', 'delivery_proof',
            'failure_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'order_number', 'confirmation_sms_sent', 'delivered_at',
            'created_at', 'updated_at'
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'customer_name', 'customer_phone', 'landmark',
            'additional_directions', 'delivery_date',
            'delivery_time_start', 'delivery_time_end', 'items_description'
        ]
    
    def create(self, validated_data):
        validated_data['vendor'] = self.context['request'].user
        validated_data['status'] = 'PENDING_CONFIRMATION'
        return super().create(validated_data)


class SMSLogSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = SMSLog
        fields = [
            'id', 'order', 'order_number', 'recipient_phone',
            'message_type', 'message_content', 'sent_at',
            'delivered', 'delivery_status', 'response_received',
            'response_content', 'response_at'
        ]
        read_only_fields = ['sent_at']


class DeliveryRouteSerializer(serializers.ModelSerializer):
    rider_name = serializers.CharField(source='rider.user.get_full_name', read_only=True)
    landmark_name = serializers.CharField(source='landmark.name', read_only=True)
    order_count = serializers.IntegerField(source='orders.count', read_only=True)
    orders_detail = OrderSerializer(source='orders', many=True, read_only=True)
    
    class Meta:
        model = DeliveryRoute
        fields = [
            'id', 'rider', 'rider_name', 'route_date',
            'landmark', 'landmark_name', 'sequence',
            'estimated_arrival', 'completed', 'completed_at',
            'order_count', 'orders_detail', 'created_at'
        ]
        read_only_fields = ['created_at', 'completed_at']


class RiderDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    preferred_landmarks_detail = LandmarkSerializer(
        source='preferred_landmarks',
        many=True,
        read_only=True
    )
    current_routes = serializers.SerializerMethodField()
    
    class Meta:
        model = Rider
        fields = [
            'id', 'full_name', 'email', 'phone_number',
            'vehicle_type', 'vehicle_registration', 'status',
            'preferred_landmarks_detail', 'total_deliveries',
            'successful_deliveries', 'failed_deliveries',
            'rating', 'success_rate', 'current_routes',
            'last_active', 'created_at'
        ]
    
    def get_current_routes(self, obj):
        from django.utils import timezone
        today = timezone.now().date()
        routes = DeliveryRoute.objects.filter(
            rider=obj,
            route_date=today,
            completed=False
        ).order_by('sequence')
        return DeliveryRouteSerializer(routes, many=True).data


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.ORDER_STATUS)
    delivery_proof = serializers.CharField(required=False, allow_blank=True)
    failure_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['status'] == 'DELIVERED' and not data.get('delivery_proof'):
            raise serializers.ValidationError({
                'delivery_proof': 'Delivery proof is required when marking as delivered'
            })
        
        if data['status'] == 'FAILED' and not data.get('failure_reason'):
            raise serializers.ValidationError({
                'failure_reason': 'Failure reason is required when marking as failed'
            })
        
        return data
    