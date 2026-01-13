from riders.models import Rider
from .models import Order, DeliveryRoute
from .sms_service import sms_service


class RiderAssignmentService:
    """Intelligent rider assignment based on landmarks and availability"""
    
    def assign_orders_to_riders(self, orders_queryset=None):
        """
        Main method to assign confirmed orders to riders
        Can be called manually or via a scheduled task
        """
        if orders_queryset is None:
            orders_queryset = Order.objects.filter(
                status='CONFIRMED',
                assigned_rider__isnull=True
            )
        
        if not orders_queryset.exists():
            return {'status': 'no_orders', 'message': 'No orders to assign'}
        
        grouped_orders = self._group_orders_by_landmark_and_date(orders_queryset)
        
        assigned_count = 0
        results = []
        
        for (landmark, delivery_date), orders in grouped_orders.items():
            result = self._assign_group_to_rider(landmark, delivery_date, orders)
            if result['success']:
                assigned_count += len(orders)
            results.append(result)
        
        return {
            'status': 'success',
            'assigned_count': assigned_count,
            'total_orders': orders_queryset.count(),
            'details': results
        }
    
    def _group_orders_by_landmark_and_date(self, orders):
        """Group orders by landmark and delivery date"""
        grouped = {}
        
        for order in orders:
            key = (order.landmark, order.delivery_date)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(order)
        
        return grouped
    
    def _assign_group_to_rider(self, landmark, delivery_date, orders):
        """Assign a group of orders to the best available rider"""
        
        available_riders = Rider.objects.filter(
            status='AVAILABLE'
        ).order_by('-rating', '-successful_deliveries')
        
        if not available_riders.exists():
            return {
                'success': False,
                'landmark': landmark.name,
                'reason': 'No available riders',
                'order_count': len(orders)
            }
        
        best_rider = self._find_best_rider(available_riders, landmark, orders)
        
        if not best_rider:
            return {
                'success': False,
                'landmark': landmark.name,
                'reason': 'No suitable rider found',
                'order_count': len(orders)
            }
        
        for order in orders:
            order.assigned_rider = best_rider
            order.status = 'ASSIGNED'
            order.save()
        
        route = self._create_delivery_route(best_rider, landmark, delivery_date, orders)
        
        sms_service.send_rider_assignment_sms(best_rider, orders)
        
        best_rider.status = 'ON_DELIVERY'
        best_rider.save()
        
        return {
            'success': True,
            'landmark': landmark.name,
            'rider': best_rider.user.get_full_name(),
            'order_count': len(orders),
            'route_id': route.id
        }
    
    def _find_best_rider(self, riders, landmark, orders):
        """
        Score riders based on:
        1. Familiarity with landmark (preferred landmarks)
        2. Current workload
        3. Performance rating
        4. Success rate
        """
        scored_riders = []
        
        for rider in riders:
            score = 0
            
            if landmark in rider.preferred_landmarks.all():
                score += 30
            
            current_assignments = Order.objects.filter(
                assigned_rider=rider,
                status__in=['ASSIGNED', 'IN_TRANSIT'],
                delivery_date=orders[0].delivery_date
            ).count()
            
            if current_assignments == 0:
                score += 25
            elif current_assignments <= 2:
                score += 15
            elif current_assignments <= 5:
                score += 5
            
            rating_score = (float(rider.rating) / 5.0) * 25
            score += rating_score
            
            success_score = (rider.success_rate / 100.0) * 20
            score += success_score
            
            scored_riders.append((rider, score))
        
        scored_riders.sort(key=lambda x: x[1], reverse=True)
        
        return scored_riders[0][0] if scored_riders else None
    
    def _create_delivery_route(self, rider, landmark, delivery_date, orders):
        """Create optimized delivery route"""
        
        existing_routes = DeliveryRoute.objects.filter(
            rider=rider,
            route_date=delivery_date
        ).order_by('-sequence')
        
        sequence = existing_routes.first().sequence + 1 if existing_routes.exists() else 1
        
        estimated_arrival = min([o.delivery_time_start for o in orders])
        
        route = DeliveryRoute.objects.create(
            rider=rider,
            route_date=delivery_date,
            landmark=landmark,
            sequence=sequence,
            estimated_arrival=estimated_arrival
        )
        
        route.orders.set(orders)
        
        return route
    
    def optimize_rider_route(self, rider, delivery_date):
        """
        Optimize the delivery sequence for a rider on a given date
        Orders routes by time windows
        """
        routes = DeliveryRoute.objects.filter(
            rider=rider,
            route_date=delivery_date,
            completed=False
        ).order_by('estimated_arrival')
        
        for idx, route in enumerate(routes, start=1):
            route.sequence = idx
            route.save()
        
        return {
            'rider': rider.user.get_full_name(),
            'date': delivery_date,
            'route_count': routes.count(),
            'routes': [
                {
                    'sequence': r.sequence,
                    'landmark': r.landmark.name,
                    'time': r.estimated_arrival.strftime('%I:%M %p'),
                    'orders': r.orders.count()
                }
                for r in routes
            ]
        }


assignment_service = RiderAssignmentService()
