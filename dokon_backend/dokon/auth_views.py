from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import StoreProfile

User = get_user_model()


def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


# ─── Register ────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    phone = request.data.get('phone', '').strip()
    password = request.data.get('password', '')
    full_name = request.data.get('full_name', '')
    store_name = request.data.get('store_name', "Kiyim Do'koni")

    if not phone or not password:
        return Response({'error': "Telefon va parol kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)

    if len(password) < 6:
        return Response({'error': "Parol kamida 6 ta belgidan iborat bo'lishi kerak"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(phone=phone).exists():
        return Response({'error': "Bu telefon raqam allaqachon ro'yxatdan o'tgan"}, status=status.HTTP_400_BAD_REQUEST)

    # STATUS = PENDING — admin tasdiqlashi kerak
    user = User.objects.create_user(
        phone=phone,
        password=password,
        full_name=full_name,
        status='pending',
    )

    StoreProfile.objects.create(
        user=user,
        store_name=store_name,
        owner_name=full_name,
        phone=phone,
    )

    # Token BERMAYMIZ — faqat pending xabar qaytaramiz
    return Response({
        'pending': True,
        'message': "Rahmat! Ma'lumotlaringiz qabul qilindi. Tez orada admin siz bilan bog'lanadi.",
        'phone': user.phone,
    }, status=status.HTTP_201_CREATED)


# ─── Login ────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    phone = request.data.get('phone', '').strip()
    password = request.data.get('password', '')

    if not phone or not password:
        return Response({'error': "Telefon va parol kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        return Response({'error': "Telefon raqam topilmadi"}, status=status.HTTP_404_NOT_FOUND)

    if not user.check_password(password):
        return Response({'error': "Parol noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)

    if not user.is_active:
        return Response({'error': "Hisobingiz bloklangan. Murojaat qiling."}, status=status.HTTP_403_FORBIDDEN)

    # Pending tekshirish
    if user.status == 'pending':
        return Response({
            'error': "Hisobingiz hali tasdiqlanmagan. Admin tez orada bog'lanadi.",
            'pending': True,
        }, status=status.HTTP_403_FORBIDDEN)

    if user.status == 'rejected':
        return Response({'error': "Hisobingiz rad etilgan. Murojaat qiling."}, status=status.HTTP_403_FORBIDDEN)

    if user.status == 'blocked':
        return Response({'error': "Hisobingiz bloklangan. Murojaat qiling."}, status=status.HTTP_403_FORBIDDEN)

    tokens = get_tokens(user)
    profile = getattr(user, 'profile', None)

    return Response({
        'user': {
            'id': str(user.id),
            'phone': user.phone,
            'full_name': user.full_name,
            'role': user.role,
            'is_subscribed': user.is_subscribed,
            'days_left': user.days_left,
            'subscription_end': str(user.subscription_end) if user.subscription_end else None,
            'store_name': profile.store_name if profile else "Do'kon",
            'avatar': profile.avatar if profile else '🏪',
        },
        **tokens,
    })


# ─── Me ──────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    return Response({
        'id': str(user.id),
        'phone': user.phone,
        'full_name': user.full_name,
        'role': user.role,
        'status': user.status,
        'is_subscribed': user.is_subscribed,
        'days_left': user.days_left,
        'subscription_end': str(user.subscription_end) if user.subscription_end else None,
        'subscription_start': str(user.subscription_start) if user.subscription_start else None,
        'store_name': profile.store_name if profile else "Do'kon",
        'avatar': profile.avatar if profile else '🏪',
    })


# ─── Change Password ──────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    old_password = request.data.get('old_password', '')
    new_password = request.data.get('new_password', '')

    if not request.user.check_password(old_password):
        return Response({'error': "Eski parol noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 6:
        return Response({'error': "Yangi parol kamida 6 ta belgidan iborat bo'lishi kerak"}, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(new_password)
    request.user.save()
    tokens = get_tokens(request.user)
    return Response({'message': "Parol muvaffaqiyatli o'zgartirildi!", **tokens})