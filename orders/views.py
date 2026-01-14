from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Landmark, Order, SMSLog, DeliveryRoute
from .serializers import (
    LandmarkSerializer, OrderSerializer, OrderCreateSerializer,
    SMSLogSerializer, DeliveryRouteSerializer, OrderStatusUpdateSerializer
)
from .sms_service import sms_service
from .assignment_service import assignment_service

class LandmarkListView(generics.ListAPIView):
    """List all landmarks"""
    queryset = Landmark.objects.all()
    serializer_class = LandmarkSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'area', 'city']
    filterset_fields = ['city', 'area']


class LandmarkDetailView(generics.RetrieveAPIView):
    """Get landmark details"""
    queryset = Landmark.objects.all()
    serializer_class = LandmarkSerializer

class OrderListCreateView(generics.ListCreateAPIView):
    """
    List all orders or create a new order
    Vendors see only their orders, staff see all
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['order_number', 'customer_name', 'customer_phone']
    filterset_fields = ['status', 'delivery_date', 'landmark']
    ordering_fields = ['created_at', 'delivery_date', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(vendor=user)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        return OrderSerializer
class OrderDetailView(generics.RetrieveUpdateAPIView):
    """Get or update order details"""
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(vendor=user)
class OrderSendConfirmationView(APIView):
    """Send confirmation SMS to customer"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        
        if not request.user.is_staff and order.vendor != request.user:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if order.status != 'PENDING_CONFIRMATION':
            return Response(
                {'error': f'Order is {order.status}, cannot send confirmation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = sms_service.send_order_confirmation_sms(order)
        
        if success:
            return Response({
                'message': 'Confirmation SMS sent successfully',
                'order_number': order.order_number,
                'customer_phone': order.customer_phone
            })
        else:
            return Response(
                {'error': 'Failed to send SMS'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderConfirmView(APIView):
    """Customer confirms order (simulating SMS response)"""
    
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        
        if order.status != 'PENDING_CONFIRMATION':
            return Response(
                {'error': 'Order cannot be confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'CONFIRMED'
        order.customer_confirmed_at = timezone.now()
        order.save()
        
        return Response({
            'message': 'Order confirmed successfully',
            'order_number': order.order_number,
            'status': order.status
        })


class OrderRescheduleView(APIView):
    """Customer requests to reschedule"""
    
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        
        if order.status != 'PENDING_CONFIRMATION':
            return Response(
                {'error': 'Order cannot be rescheduled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'RESCHEDULE_REQUESTED'
        order.save()
        
        return Response({
            'message': 'Reschedule request received',
            'order_number': order.order_number,
            'status': order.status
        })
class OrderUpdateStatusView(APIView):
    """Update order status (for riders)"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        serializer = OrderStatusUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        order.status = validated_data['status']
        
        if validated_data['status'] == 'DELIVERED':
            order.delivered_at = timezone.now()
            order.delivery_proof = validated_data.get('delivery_proof', '')
            
            if order.assigned_rider:
                rider = order.assigned_rider
                rider.total_deliveries += 1
                rider.successful_deliveries += 1
                rider.save()
            
            sms_service.send_delivery_success_sms(order)
        
        elif validated_data['status'] == 'FAILED':
            order.failure_reason = validated_data.get('failure_reason', '')
            
            if order.assigned_rider:
                rider = order.assigned_rider
                rider.total_deliveries += 1
                rider.failed_deliveries += 1
                rider.save()
            
            sms_service.send_delivery_failed_sms(order)
        
        order.save()
        
        return Response({
            'message': f'Order status updated to {order.get_status_display()}',
            'order': OrderSerializer(order).data
        })

class AssignOrdersView(APIView):
    """Trigger automatic rider assignment"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can trigger assignments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        result = assignment_service.assign_orders_to_riders()
        
        return Response({
            'message': 'Assignment completed',
            'result': result
        })

class ManualAssignOrderView(APIView):
    """Manually assign an order to a specific rider"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can manually assign orders'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        order = get_object_or_404(Order, pk=pk)
        rider_id = request.data.get('rider_id')
        
        if not rider_id:
            return Response(
                {'error': 'rider_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from riders.models import Rider
        rider = get_object_or_404(Rider, pk=rider_id)
        
        order.assigned_rider = rider
        order.status = 'ASSIGNED'
        order.save()
        
        route = DeliveryRoute.objects.create(
            rider=rider,
            route_date=order.delivery_date,
            landmark=order.landmark,
            sequence=1,
            estimated_arrival=order.delivery_time_start
        )
        route.orders.add(order)
        
        sms_service.send_rider_assignment_sms(rider, [order])
        
        return Response({
            'message': 'Order assigned successfully',
            'order': OrderSerializer(order).data
        })

class SMSLogListView(generics.ListAPIView):
    """List SMS logs"""
    permission_classes = [IsAuthenticated]
    serializer_class = SMSLogSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['message_type', 'delivered', 'response_received']
    ordering = ['-sent_at']
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return SMSLog.objects.all()
        return SMSLog.objects.filter(order__vendor=self.request.user)


class SMSWebhookView(APIView):
    """Handle incoming SMS from Africa's Talking"""
    
    def post(self, request):
        phone = request.data.get('from')
        message = request.data.get('text', '').strip()
        
        if not phone or not message:
            return Response({'error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = sms_service.handle_incoming_sms(phone, message)
        
        return Response(result)


class DeliveryRouteListView(generics.ListAPIView):
    """List delivery routes"""
    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryRouteSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['rider', 'route_date', 'completed']
    ordering = ['route_date', 'sequence']
    
    def get_queryset(self):
        return DeliveryRoute.objects.all()


class DeliveryRouteDetailView(generics.RetrieveUpdateAPIView):
    """Get or update route details"""
    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryRouteSerializer
    queryset = DeliveryRoute.objects.all()


class RiderRoutesView(APIView):
    """Get routes for a specific rider on a specific date"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, rider_id):
        from riders.models import Rider
        rider = get_object_or_404(Rider, pk=rider_id)
        
        date_str = request.query_params.get('date')
        if date_str:
            from datetime import datetime
            delivery_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            delivery_date = timezone.now().date()
        
        routes = DeliveryRoute.objects.filter(
            rider=rider,
            route_date=delivery_date
        ).order_by('sequence')
        
        serializer = DeliveryRouteSerializer(routes, many=True)
        
        return Response({
            'rider': rider.user.get_full_name(),
            'date': delivery_date,
            'routes': serializer.data
        })


class DashboardStatsView(APIView):
    """Get dashboard statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        if user.is_staff:
            total_orders = Order.objects.count()
            pending = Order.objects.filter(status='PENDING_CONFIRMATION').count()
            confirmed = Order.objects.filter(status='CONFIRMED').count()
            in_transit = Order.objects.filter(status='IN_TRANSIT').count()
            delivered_today = Order.objects.filter(
                status='DELIVERED',
                delivered_at__date=today
            ).count()
            
            from riders.models import Rider
            available_riders = Rider.objects.filter(status='AVAILABLE').count()
            on_delivery = Rider.objects.filter(status='ON_DELIVERY').count()
            
            return Response({
                'total_orders': total_orders,
                'pending_confirmation': pending,
                'confirmed': confirmed,
                'in_transit': in_transit,
                'delivered_today': delivered_today,
                'available_riders': available_riders,
                'riders_on_delivery': on_delivery
            })
        else:
            total_orders = Order.objects.filter(vendor=user).count()
            pending = Order.objects.filter(vendor=user, status='PENDING_CONFIRMATION').count()
            delivered = Order.objects.filter(vendor=user, status='DELIVERED').count()
            
            return Response({
                'total_orders': total_orders,
                'pending_confirmation': pending,
                'delivered': delivered
            })
        