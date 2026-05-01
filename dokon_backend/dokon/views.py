from django.db.models import Sum, Q, F
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    StoreProfile, Customer, Product, ProductSize,
    Sale, SaleItem, Debt, DebtPayment, Expense
)
from .serializers import (
    StoreProfileSerializer, CustomerSerializer, ProductSerializer,
    SaleSerializer, DebtSerializer, DebtPaymentSerializer,
    ExpenseSerializer
)


# ─── Store Profile ────────────────────────────────────────────────────────────

@api_view(['GET', 'PUT', 'PATCH'])
def profile_view(request):
    profile, _ = StoreProfile.objects.get_or_create(user=request.user)
    if request.method == 'GET':
        return Response(StoreProfileSerializer(profile).data)
    serializer = StoreProfileSerializer(profile, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    u = request.user

    if not hasattr(u, 'is_subscribed') or not u.is_subscribed:
        return Response(
            {'error': "Obuna muddati tugagan. Iltimos yangilang.", 'subscription_expired': True},
            status=status.HTTP_403_FORBIDDEN
        )

    today = timezone.localdate()
    month_start = today.replace(day=1)
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Qaytarilmagan sotuvlar
    today_sales = Sale.objects.filter(user=u, date__gte=today_start, is_returned=False)
    today_revenue = today_sales.aggregate(t=Sum('total_amount'))['t'] or 0
    month_sales = Sale.objects.filter(user=u, date__date__gte=month_start, is_returned=False)
    month_revenue = month_sales.aggregate(t=Sum('total_amount'))['t'] or 0

    # Qaytarishlar statistikasi
    today_returns = Sale.objects.filter(user=u, returned_at__date=today, is_returned=True)
    today_returned_amount = today_returns.aggregate(t=Sum('returned_amount'))['t'] or 0

    total_qty = ProductSize.objects.filter(product__user=u).aggregate(t=Sum('quantity'))['t'] or 0
    unique_products = Product.objects.filter(user=u).count()
    total_customers = Customer.objects.filter(user=u).count()
    debts = Debt.objects.filter(user=u).exclude(status="to'langan")
    total_debt = debts.aggregate(t=Sum('remaining_amount'))['t'] or 0

    profile, _ = StoreProfile.objects.get_or_create(user=u)
    low_stock_count = sum(
        1 for p in Product.objects.filter(user=u).prefetch_related('sizes')
        if p.total_quantity < profile.low_stock_alert
    )
    recent_sales = Sale.objects.filter(
        user=u, is_returned=False
    ).select_related('customer').prefetch_related('items')[:5]

    return Response({
        'today_revenue': today_revenue,
        'today_sales_count': today_sales.count(),
        'today_returned_amount': float(today_returned_amount),
        'month_revenue': month_revenue,
        'month_sales_count': month_sales.count(),
        'total_products': total_qty,
        'unique_products': unique_products,
        'total_customers': total_customers,
        'total_debt': total_debt,
        'unpaid_debts_count': debts.count(),
        'low_stock_count': low_stock_count,
        'days_left': u.days_left,
        'recent_sales': SaleSerializer(recent_sales, many=True).data,
    })


# ─── Customer ─────────────────────────────────────────────────────────────────

class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Customer.objects.filter(user=self.request.user)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(phone__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─── Product ──────────────────────────────────────────────────────────────────

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Product.objects.filter(user=self.request.user).prefetch_related('sizes')
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(brand__icontains=search) | Q(barcode__icontains=search))
        if category and category != 'Hammasi':
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─── Sale ─────────────────────────────────────────────────────────────────────

class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = Sale.objects.filter(
            user=self.request.user,
            is_returned=False  # Qaytarilganlarni yashirish
        ).select_related('customer').prefetch_related('items')
        search = self.request.query_params.get('search')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if search:
            qs = qs.filter(Q(customer__name__icontains=search))
        if date_from and date_to:
            qs = qs.filter(date__date__gte=date_from, date__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─── Debt ─────────────────────────────────────────────────────────────────────

class DebtViewSet(viewsets.ModelViewSet):
    serializer_class = DebtSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Debt.objects.filter(user=self.request.user).select_related('customer', 'sale').prefetch_related('payments')
        status_filter = self.request.query_params.get('status')
        if status_filter and status_filter != 'all':
            status_map = {
                'unpaid': "to'lanmagan",
                'partial': "qisman to'langan",
                'paid': "to'langan",
            }
            qs = qs.filter(status=status_map.get(status_filter, status_filter))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        debt = self.get_object()
        amount = request.data.get('amount')
        if not amount:
            return Response({'error': "Summa kiritilmagan"}, status=status.HTTP_400_BAD_REQUEST)
        amount = float(amount)
        if amount <= 0:
            return Response({'error': "Summa 0 dan katta bo'lishi kerak"}, status=status.HTTP_400_BAD_REQUEST)
        if amount > float(debt.remaining_amount):
            return Response({'error': "To'lov summasi qarz miqdoridan katta"}, status=status.HTTP_400_BAD_REQUEST)

        DebtPayment.objects.create(debt=debt, amount=amount)
        debt.paid_amount += amount
        debt.remaining_amount -= amount
        if debt.remaining_amount <= 0:
            debt.remaining_amount = 0
            debt.status = "to'langan"
        elif debt.paid_amount > 0:
            debt.status = "qisman to'langan"
        debt.save()

        customer = debt.customer
        customer.total_debt = max(0, float(customer.total_debt) - amount)
        customer.save()
        return Response(DebtSerializer(debt).data)


# ─── Expense ──────────────────────────────────────────────────────────────────

class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Expense.objects.filter(user=self.request.user)
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        month = self.request.query_params.get('month')
        category = self.request.query_params.get('category')
        if date_from and date_to:
            qs = qs.filter(date__gte=date_from, date__lte=date_to)
        elif month:
            qs = qs.filter(date__year=month[:4], date__month=month[5:7])
        if category and category != 'Hammasi':
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─── Reports ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
def reports_view(request):
    u = request.user
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    month = request.query_params.get('month', timezone.localdate().strftime('%Y-%m'))

    if date_from and date_to:
        month_sales = Sale.objects.filter(
            user=u, date__date__gte=date_from, date__date__lte=date_to, is_returned=False)
        month_returns = Sale.objects.filter(
            user=u, returned_at__date__gte=date_from, returned_at__date__lte=date_to, is_returned=True)
        month_expenses = Expense.objects.filter(user=u, date__gte=date_from, date__lte=date_to)
    else:
        year, mon = int(month[:4]), int(month[5:7])
        month_sales = Sale.objects.filter(
            user=u, date__year=year, date__month=mon, is_returned=False)
        month_returns = Sale.objects.filter(
            user=u, returned_at__year=year, returned_at__month=mon, is_returned=True)
        month_expenses = Expense.objects.filter(user=u, date__year=year, date__month=mon)

    total_revenue = month_sales.aggregate(t=Sum('total_amount'))['t'] or 0
    total_expenses_amount = month_expenses.aggregate(t=Sum('amount'))['t'] or 0

    # Qaytarishlar
    total_returned = month_returns.aggregate(t=Sum('returned_amount'))['t'] or 0

    # Ayirboshlash foyda/zarari
    exchange_sales = Sale.objects.filter(
        user=u, note__startswith='Ayirboshlash:',
        **({'date__date__gte': date_from, 'date__date__lte': date_to} if date_from and date_to
           else {'date__year': int(month[:4]), 'date__month': int(month[5:7])})
    )
    exchange_revenue = exchange_sales.aggregate(t=Sum('total_amount'))['t'] or 0

    total_cost = 0
    for sale in month_sales.prefetch_related('items__product'):
        for item in sale.items.all():
            if item.product:
                total_cost += float(item.product.buy_price) * item.quantity

    gross_profit = float(total_revenue) - total_cost
    net_profit = gross_profit - float(total_expenses_amount)

    # Qaytarishdan keyin tuzatilgan foyda
    net_profit_after_returns = net_profit - float(total_returned) + float(exchange_revenue)

    payment_data = {}
    for method, label in [('naqd', 'Naqd'), ('karta', 'Karta'), ('nasiya', 'Nasiya')]:
        val = month_sales.filter(payment_method=method).aggregate(t=Sum('total_amount'))['t'] or 0
        if val > 0:
            payment_data[label] = float(val)

    top_items = (
        SaleItem.objects.filter(sale__in=month_sales)
        .values('product_name')
        .annotate(total_qty=Sum('quantity'), total_rev=Sum(F('price') * F('quantity')))
        .order_by('-total_rev')[:5]
    )

    expense_by_cat = {}
    for exp in month_expenses:
        expense_by_cat[exp.category] = expense_by_cat.get(exp.category, 0) + float(exp.amount)

    return Response({
        'total_revenue': float(total_revenue),
        'total_expenses': float(total_expenses_amount),
        'total_cost': total_cost,
        'gross_profit': gross_profit,
        'net_profit': net_profit,
        'total_returned': float(total_returned),
        'returns_count': month_returns.count(),
        'exchange_revenue': float(exchange_revenue),
        'net_profit_after_returns': net_profit_after_returns,
        'sales_count': month_sales.count(),
        'expenses_count': month_expenses.count(),
        'payment_methods': payment_data,
        'top_products': [
            {'name': i['product_name'], 'quantity': i['total_qty'], 'revenue': float(i['total_rev'])}
            for i in top_items
        ],
        'expense_by_category': expense_by_cat,
    })