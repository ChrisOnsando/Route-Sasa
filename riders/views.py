from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from .models import Rider
from orders.serializers import RiderSimpleSerializer, RiderDetailSerializer


class RiderListView(generics.ListAPIView):
    """List all riders"""
    permission_classes = [IsAuthenticated]
    serializer_class = RiderSimpleSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['user__first_name', 'user__last_name', 'phone_number']
    filterset_fields = ['status', 'vehicle_type']
    ordering_fields = ['rating', 'total_deliveries', 'created_at']
    ordering = ['-rating']
    
    def get_queryset(self):
        return Rider.objects.all()


class RiderDetailView(generics.RetrieveUpdateAPIView):
    """Get or update rider details"""
    permission_classes = [IsAuthenticated]
    serializer_class = RiderDetailSerializer
    queryset = Rider.objects.all()


class RiderAvailableListView(generics.ListAPIView):
    """List only available riders"""
    permission_classes = [IsAuthenticated]
    serializer_class = RiderSimpleSerializer
    
    def get_queryset(self):
        return Rider.objects.filter(status='AVAILABLE').order_by('-rating')


class RiderUpdateStatusView(APIView):
    """Update rider status (available/offline/on_delivery)"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        rider = get_object_or_404(Rider, pk=pk)
        
        new_status = request.data.get('status')
        if new_status not in ['AVAILABLE', 'ON_DELIVERY', 'OFFLINE']:
            return Response(
                {'error': 'Invalid status. Must be AVAILABLE, ON_DELIVERY, or OFFLINE'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rider.status = new_status
        rider.save()
        
        return Response({
            'message': f'Rider status updated to {new_status}',
            'rider': RiderSimpleSerializer(rider).data
        })


class RiderUpdateLocationView(APIView):
    """Update rider's current location"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        rider = get_object_or_404(Rider, pk=pk)
        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response(
                {'error': 'latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            rider.current_location_lat = float(latitude)
            rider.current_location_lng = float(longitude)
            rider.save()
            
            return Response({
                'message': 'Location updated successfully',
                'latitude': rider.current_location_lat,
                'longitude': rider.current_location_lng
            })
        except ValueError:
            return Response(
                {'error': 'Invalid latitude or longitude values'},
                status=status.HTTP_400_BAD_REQUEST
            )
        