import stripe
from core.config import settings

stripe.api_key = settings.stripe_api_key

class PaymentService:
    async def create_checkout_session(self, amount: float, booking_id: int) -> str:
        """
        Creates a Stripe Checkout Session and returns the URL.
        """
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'Booking #{booking_id}',
                        },
                        'unit_amount': int(amount * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f'https://example.com/success?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url='https://example.com/cancel',
            )
            return session.url
        except Exception as e:
            print(f"Stripe error: {e}")
            return None

payment_service = PaymentService()
