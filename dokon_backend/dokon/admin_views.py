from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import User, StoreProfile, PaymentHistory, Notification, Sale


def is_admin(user):
    return user.role in ('super_admin', 'support')


def is_super_admin(user):
    return user.role == 'super_admin'


# ─── Admin Login ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login_view(request):
    """Yashirin admin login"""
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import RefreshToken

    User = get_user_model()
    phone = request.data.get('phone', '').strip()
    password = request.data.get('password', '')
    secret_key = request.data.get('secret_key', '')

    # Maxfiy kalit tekshirish
    if secret_key != 'JAVLON_DEV':
        return Response({'error': 'Noto\'g\'ri maxfiy kalit'}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        return Response({'error': 'Foydalanuvchi topilmadi'}, status=status.HTTP_404_NOT_FOUND)

    if not user.check_password(password):
        return Response({'error': 'Parol noto\'g\'ri'}, status=status.HTTP_400_BAD_REQUEST)

    if user.role not in ['super_admin', 'support']:
        return Response({'error': "Admin huquqi yoq"}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'role': user.role,
        'name': user.full_name,
    })


# ─── Dashboard ───────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    if not is_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    today = timezone.localdate()
    total_users = User.objects.filter(role='user').count()
    pending = User.objects.filter(role='user', status='pending').count()
    active = User.objects.filter(role='user', status='active').count()
    blocked = User.objects.filter(role='user', status='blocked').count()
    expiring_soon = User.objects.filter(
        role='user', status='active',
        subscription_end__lte=today + timedelta(days=30),
        subscription_end__gte=today
    ).count()

    today_revenue = Sale.objects.filter(
        date__date=today
    ).aggregate(t=Sum('total_amount'))['t'] or 0

    month_revenue = Sale.objects.filter(
        date__date__gte=today.replace(day=1)
    ).aggregate(t=Sum('total_amount'))['t'] or 0

    return Response({
        'total_users': total_users,
        'pending': pending,
        'active': active,
        'blocked': blocked,
        'expiring_soon': expiring_soon,
        'today_revenue': float(today_revenue),
        'month_revenue': float(month_revenue),
    })


# ─── Users List ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_users_list(request):
    if not is_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    status_filter = request.query_params.get('status', 'all')
    search = request.query_params.get('search', '')

    qs = User.objects.filter(role='user').select_related('profile')

    if status_filter != 'all':
        qs = qs.filter(status=status_filter)

    if search:
        qs = qs.filter(
            Q(phone__icontains=search) |
            Q(full_name__icontains=search) |
            Q(profile__store_name__icontains=search)
        )

    users = []
    for u in qs.order_by('-created_at'):
        profile = getattr(u, 'profile', None)
        users.append({
            'id': str(u.id),
            'phone': u.phone,
            'full_name': u.full_name,
            'store_name': profile.store_name if profile else '',
            'owner_name': profile.owner_name if profile else '',
            'status': u.status,
            'is_subscribed': u.is_subscribed,
            'days_left': u.days_left,
            'subscription_end': str(u.subscription_end) if u.subscription_end else None,
            'created_at': str(u.created_at.date()),
        })

    return Response(users)


# ─── User Detail ─────────────────────────────────────────────────────────────

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_user_detail(request, user_id):
    if not is_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        profile = getattr(user, 'profile', None)
        payments = PaymentHistory.objects.filter(user=user)
        return Response({
            'id': str(user.id),
            'phone': user.phone,
            'full_name': user.full_name,
            'store_name': profile.store_name if profile else '',
            'owner_name': profile.owner_name if profile else '',
            'status': user.status,
            'is_subscribed': user.is_subscribed,
            'days_left': user.days_left,
            'subscription_start': str(user.subscription_start) if user.subscription_start else None,
            'subscription_end': str(user.subscription_end) if user.subscription_end else None,
            'created_at': str(user.created_at.date()),
            'payments': [
                {
                    'amount': float(p.amount),
                    'payment_type': p.payment_type,
                    'months_added': p.months_added,
                    'note': p.note,
                    'date': str(p.created_at.date()),
                }
                for p in payments
            ],
        })

    # PATCH
    if 'status' in request.data:
        user.status = request.data['status']
    if 'full_name' in request.data:
        user.full_name = request.data['full_name']
    if 'password' in request.data and is_super_admin(request.user):
        user.set_password(request.data['password'])
    user.save()

    if 'store_name' in request.data:
        profile, _ = StoreProfile.objects.get_or_create(user=user)
        profile.store_name = request.data['store_name']
        profile.save()

    return Response({'success': True})


# ─── Approve / Reject ────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_approve_user(request, user_id):
    if not is_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

    user.status = 'active'
    user.save()
    return Response({'success': True, 'message': f"{user.phone} tasdiqlandi!"})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_reject_user(request, user_id):
    if not is_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

    user.status = 'rejected'
    user.save()
    return Response({'success': True})


# ─── Subscription ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_add_subscription(request, user_id):
    if not is_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

    months = int(request.data.get('months', 12))
    amount = float(request.data.get('amount', 0))
    payment_type = request.data.get('payment_type', 'cash')
    note = request.data.get('note', '')

    today = timezone.localdate()
    days = months * 30

    if user.subscription_end and user.subscription_end > today:
        user.subscription_end = user.subscription_end + timedelta(days=days)
    else:
        user.subscription_start = today
        user.subscription_end = today + timedelta(days=days)

    if user.status != 'active':
        user.status = 'active'
    user.save()

    # To'lov tarixini saqlash
    if amount > 0:
        PaymentHistory.objects.create(
            user=user,
            amount=amount,
            payment_type=payment_type,
            months_added=months,
            note=note,
            created_by=request.user,
        )

    return Response({
        'success': True,
        'subscription_end': str(user.subscription_end),
        'days_left': user.days_left,
        'message': f"{months} oy obuna berildi!",
    })


# ─── Notifications ────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def admin_notifications(request):
    if not is_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        notifs = Notification.objects.all()[:20]
        return Response([{
            'id': n.id,
            'title': n.title,
            'body': n.body,
            'target': n.target,
            'sent_count': n.sent_count,
            'date': str(n.created_at.date()),
        } for n in notifs])

    # POST — xabar yuborish
    title = request.data.get('title', '')
    body = request.data.get('body', '')
    target = request.data.get('target', 'all')

    if not title or not body:
        return Response({'error': 'Mavzu va matn kiritilishi shart'}, status=status.HTTP_400_BAD_REQUEST)

    # Target bo'yicha userlar
    qs = User.objects.filter(role='user')
    if target == 'active':
        qs = qs.filter(status='active')
    elif target == 'pending':
        qs = qs.filter(status='pending')
    elif target == 'expiring':
        today = timezone.localdate()
        qs = qs.filter(
            status='active',
            subscription_end__lte=today + timedelta(days=30),
            subscription_end__gte=today
        )

    count = qs.count()
    notif = Notification.objects.create(
        title=title, body=body, target=target,
        sent_by=request.user, sent_count=count,
    )

    return Response({
        'success': True,
        'sent_count': count,
        'message': f"{count} ta foydalanuvchiga xabar yuborildi!",
    })


# ─── Staff Management (Super Admin only) ─────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_staff_list(request):
    """Support va adminlar ro'yxati"""
    if not is_super_admin(request.user):
        return Response({'error': 'Faqat Super Admin uchun'}, status=status.HTTP_403_FORBIDDEN)

    staff = User.objects.filter(role__in=['support', 'super_admin']).order_by('role', '-id')
    result = []
    for u in staff:
        result.append({
            'id': str(u.id),
            'phone': u.phone,
            'full_name': u.full_name,
            'role': u.role,
            'status': u.status,
            'is_active': u.is_active,
            'created_at': str(u.created_at.date()),
            'permissions': _get_permissions(u.role),
        })
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_staff_create(request):
    """Yangi support qo'shish"""
    if not is_super_admin(request.user):
        return Response({'error': 'Faqat Super Admin uchun'}, status=status.HTTP_403_FORBIDDEN)

    phone = request.data.get('phone', '').strip()
    password = request.data.get('password', '')
    full_name = request.data.get('full_name', '')
    role = request.data.get('role', 'support')

    if not phone or not password:
        return Response({'error': "Telefon va parol kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)

    if role not in ('support', 'super_admin'):
        return Response({'error': "Rol noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(phone=phone).exists():
        return Response({'error': "Bu telefon allaqachon mavjud"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        phone=phone,
        password=password,
        full_name=full_name,
        role=role,
        status='active',
    )
    from .models import StoreProfile
    StoreProfile.objects.create(user=user, store_name='Admin', owner_name=full_name)

    return Response({
        'success': True,
        'id': str(user.id),
        'phone': user.phone,
        'role': user.role,
        'permissions': _get_permissions(user.role),
        'message': f"{full_name} ({role}) qo'shildi!",
    })


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def admin_staff_detail(request, staff_id):
    """Support ma"lumotlarini o'zgartirish yoki o"chirish"""
    if not is_super_admin(request.user):
        return Response({'error': 'Faqat Super Admin uchun'}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=staff_id, role__in=['support', 'super_admin'])
    except User.DoesNotExist:
        return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

    # O"zini o'chirishga yo"l qo'ymaslik
    if str(user.id) == str(request.user.id) and request.method == 'DELETE':
        return Response({'error': "Oz hisobingizni ochira olmaysiz"}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        user.delete()
        return Response({'success': True, 'message': "O'chirildi!"})

    # PATCH
    if 'full_name' in request.data:
        user.full_name = request.data['full_name']
    if 'password' in request.data:
        user.set_password(request.data['password'])
    if 'role' in request.data and request.data['role'] in ('support', 'super_admin'):
        user.role = request.data['role']
    if 'is_active' in request.data:
        user.is_active = request.data['is_active']
    user.save()

    return Response({
        'success': True,
        'permissions': _get_permissions(user.role),
        'message': "Saqlandi!",
    })


def _get_permissions(role):
    """Rol bo'yicha ruxsatlar"""
    if role == 'super_admin':
        return {
            'view_dashboard': True,
            'manage_users': True,
            'view_billing': True,
            'send_notifications': True,
            'manage_staff': True,
            'view_settings': True,
        }
    elif role == 'support':
        return {
            'view_dashboard': True,
            'manage_users': True,      # Arizalarni ko'rish va tasdiqlash
            'view_billing': False,     # Moliyani ko'rmasligi
            'send_notifications': True,
            'manage_staff': False,     # Staff qo'sha olmaydi
            'view_settings': False,
        }
    return {}


# ─── Admin Management (faqat Super Admin) ────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_list(request):
    """Barcha adminlar ro'yxati"""
    if not is_super_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    admins = User.objects.filter(role__in=['super_admin', 'support']).order_by('role', 'created_at')
    result = []
    for u in admins:
        result.append({
            'id': str(u.id),
            'phone': u.phone,
            'full_name': u.full_name,
            'role': u.role,
            'status': u.status,
            'is_active': u.is_active,
            'created_at': str(u.created_at.date()),
            'permissions': _get_permissions(u.role),
        })
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_create(request):
    """Yangi support yoki admin qo'shish"""
    if not is_super_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    phone = request.data.get('phone', '').strip()
    password = request.data.get('password', '')
    full_name = request.data.get('full_name', '')
    role = request.data.get('role', 'support')

    if not phone or not password:
        return Response({'error': "Telefon va parol kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)

    if role not in ['support', 'super_admin']:
        return Response({'error': "Notogri rol"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(phone=phone).exists():
        return Response({'error': "Bu telefon allaqachon mavjud"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        phone=phone,
        password=password,
        full_name=full_name,
        role=role,
        status='active',
        is_staff=True,
    )

    return Response({
        'success': True,
        'id': str(user.id),
        'phone': user.phone,
        'role': user.role,
        'message': f"{_role_name(role)} muvaffaqiyatli qo'shildi!",
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def admin_manage(request, admin_id):
    """Adminni tahrirlash yoki o'chirish"""
    if not is_super_admin(request.user):
        return Response({'error': "Ruxsat yoq"}, status=status.HTTP_403_FORBIDDEN)

    try:
        admin = User.objects.get(id=admin_id, role__in=['support', 'super_admin'])
    except User.DoesNotExist:
        return Response({'error': "Admin topilmadi"}, status=status.HTTP_404_NOT_FOUND)

    # O'zini o'chira olmaydi
    if str(admin.id) == str(request.user.id):
        return Response({'error': 'Ruxsat yoq'}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        admin.delete()
        return Response({'success': True, 'message': "Admin ochirildi"})

    # PATCH
    if 'password' in request.data:
        admin.set_password(request.data['password'])
    if 'full_name' in request.data:
        admin.full_name = request.data['full_name']
    if 'is_active' in request.data:
        admin.is_active = request.data['is_active']
    admin.save()

    return Response({'success': True, 'message': "Saqlandi!"})


def _get_permissions(role):
    if role == 'super_admin':
        return {
            'view_dashboard': True,
            'manage_users': True,
            'approve_users': True,
            'billing': True,
            'notifications': True,
            'manage_admins': True,
            'view_revenue': True,
        }
    else:  # support
        return {
            'view_dashboard': True,
            'manage_users': False,
            'approve_users': True,
            'billing': False,
            'notifications': False,
            'manage_admins': False,
            'view_revenue': False,
        }


def _role_name(role):
    return 'Super Admin' if role == 'super_admin' else 'Support'