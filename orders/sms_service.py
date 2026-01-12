import africastalking
from django.conf import settings
from django.utils import timezone
from .models import SMSLog


class SMSService:
    """Handle all SMS communications via Africa's Talking"""
    
    def __init__(self):

        africastalking.initialize(
            username=settings.AT_USERNAME,
            api_key=settings.AT_API_KEY
        )
        self.sms = africastalking.SMS
    
    def send_order_confirmation_sms(self, order):
        """Send order confirmation SMS to customer"""
        
        message = (
            f"Hello {order.customer_name}! "
            f"Your order #{order.order_number} will be delivered on {order.delivery_date.strftime('%d/%m/%Y')} "
            f"between {order.delivery_time_start.strftime('%I:%M%p')} - {order.delivery_time_end.strftime('%I:%M%p')} "
            f"near {order.landmark.name}. "
            f"Reply 1 to CONFIRM or 2 to RESCHEDULE."
        )
        
        return self._send_sms(
            phone=order.customer_phone,
            message=message,
            order=order,
            message_type='CONFIRMATION'
        )
    
    def send_rider_assignment_sms(self, rider, orders):
        """Notify rider of new delivery assignment"""
        
        landmark_name = orders[0].landmark.name if orders else "your area"
        order_count = len(orders)
        start_time = min([o.delivery_time_start for o in orders])
        
        message = (
            f"New delivery assignment! "
            f"{order_count} stop(s) near {landmark_name}. "
            f"Start at {start_time.strftime('%I:%M%p')}. "
            f"Check your dashboard for details."
        )
        
        return self._send_sms(
            phone=rider.phone_number,
            message=message,
            order=orders[0] if orders else None,
            message_type='RIDER_ASSIGNMENT'
        )
    
    def send_delivery_success_sms(self, order):
        """Notify customer and vendor of successful delivery"""
        
        customer_message = (
            f"Your order #{order.order_number} has been delivered successfully. "
            f"Thank you for your business!"
        )
        
        vendor_message = (
            f"Order #{order.order_number} to {order.customer_name} "
            f"delivered successfully at {order.delivered_at.strftime('%I:%M%p')}."
        )
        
        customer_result = self._send_sms(
            phone=order.customer_phone,
            message=customer_message,
            order=order,
            message_type='DELIVERY_SUCCESS'
        )
        
        vendor_result = self._send_sms(
            phone=order.vendor.profile.phone if hasattr(order.vendor, 'profile') else '',
            message=vendor_message,
            order=order,
            message_type='DELIVERY_SUCCESS'
        )
        
        return customer_result and vendor_result
    
    def send_delivery_failed_sms(self, order):
        """Notify vendor of failed delivery"""
        
        message = (
            f"Delivery failed for order #{order.order_number} to {order.customer_name}. "
            f"Reason: {order.failure_reason}. "
            f"Please contact customer at {order.customer_phone}."
        )
        
        return self._send_sms(
            phone=order.vendor.profile.phone if hasattr(order.vendor, 'profile') else '',
            message=message,
            order=order,
            message_type='DELIVERY_FAILED'
        )
    
    def _send_sms(self, phone, message, order, message_type):
        """Internal method to send SMS and log"""
        
        try:
            if not phone.startswith('+'):
                if phone.startswith('0'):
                    phone = f"+254{phone[1:]}"
                elif phone.startswith('254'):
                    phone = f"+{phone}"
                else:
                    phone = f"+254{phone}"
            
            response = self.sms.send(
                message=message,
                recipients=[phone],
                sender_id=settings.AT_SENDER_ID
            )
            
            sms_log = SMSLog.objects.create(
                order=order,
                recipient_phone=phone,
                message_type=message_type,
                message_content=message,
                delivered=True,
                delivery_status='Sent'
            )
            
            if message_type == 'CONFIRMATION' and order:
                order.confirmation_sms_sent = True
                order.confirmation_sms_sent_at = timezone.now()
                order.save()
            
            print(f"SMS sent successfully: {response}")
            return True
            
        except Exception as e:
            print(f"SMS sending failed: {str(e)}")
            
            if order:
                SMSLog.objects.create(
                    order=order,
                    recipient_phone=phone,
                    message_type=message_type,
                    message_content=message,
                    delivered=False,
                    delivery_status=f'Failed: {str(e)}'
                )
            
            return False
    
    def handle_incoming_sms(self, phone, message):
        """Handle incoming SMS responses from customers"""
        
        from .models import Order
        
        order = Order.objects.filter(
            customer_phone__icontains=phone.replace('+254', '0').replace('+', ''),
            status='PENDING_CONFIRMATION'
        ).order_by('-created_at').first()
        
        if not order:
            return {'status': 'error', 'message': 'No pending order found'}
        
        response = message.strip()
        
        if response == '1':
            order.status = 'CONFIRMED'
            order.customer_confirmed_at = timezone.now()
            order.save()
            
            sms_log = order.sms_logs.filter(message_type='CONFIRMATION').first()
            if sms_log:
                sms_log.response_received = True
                sms_log.response_content = '1'
                sms_log.response_at = timezone.now()
                sms_log.save()
            
            return {'status': 'success', 'message': 'Order confirmed', 'order_id': order.id}
            
        elif response == '2':
            order.status = 'RESCHEDULE_REQUESTED'
            order.save()
            
            sms_log = order.sms_logs.filter(message_type='CONFIRMATION').first()
            if sms_log:
                sms_log.response_received = True
                sms_log.response_content = '2'
                sms_log.response_at = timezone.now()
                sms_log.save()
            
            follow_up = f"We'll contact you shortly to reschedule order #{order.order_number}."
            self._send_sms(phone, follow_up, order, 'CONFIRMATION')
            
            return {'status': 'success', 'message': 'Reschedule requested', 'order_id': order.id}
        
        return {'status': 'error', 'message': 'Invalid response. Reply 1 to confirm or 2 to reschedule.'}


sms_service = SMSService()
