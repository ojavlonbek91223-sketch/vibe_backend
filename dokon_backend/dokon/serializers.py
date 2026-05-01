from rest_framework import serializers
from .models import (
    StoreProfile, Customer, Product, ProductSize,
    Sale, SaleItem, Debt, DebtPayment, Expense
)


class StoreProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreProfile
        fields = '__all__'


# ─── Customer ────────────────────────────────────────────────────────────────

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'address',
            'total_purchases', 'total_debt', 'created_at'
        ]
        read_only_fields = ['total_purchases', 'total_debt', 'created_at']


# ─── Product ─────────────────────────────────────────────────────────────────

class ProductSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSize
        fields = ['id', 'size', 'quantity']


class ProductSerializer(serializers.ModelSerializer):
    sizes = ProductSizeSerializer(many=True)
    total_quantity = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'brand',
            'buy_price', 'sell_price', 'sizes', 'colors',
            'barcode', 'created_at', 'total_quantity'
        ]
        read_only_fields = ['created_at', 'total_quantity']

    def create(self, validated_data):
        sizes_data = validated_data.pop('sizes', [])
        product = Product.objects.create(**validated_data)
        for size_data in sizes_data:
            ProductSize.objects.create(product=product, **size_data)
        return product

    def update(self, instance, validated_data):
        sizes_data = validated_data.pop('sizes', None)

        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Replace sizes
        if sizes_data is not None:
            instance.sizes.all().delete()
            for size_data in sizes_data:
                ProductSize.objects.create(product=instance, **size_data)

        return instance


# ─── Sale ─────────────────────────────────────────────────────────────────────

class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'size', 'color', 'quantity', 'price']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'customer_name', 'items',
            'total_amount', 'paid_amount', 'discount',
            'payment_method', 'date'
        ]
        read_only_fields = ['date']

    def get_customer_name(self, obj):
        return obj.customer.name if obj.customer else None

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sale = Sale.objects.create(**validated_data)

        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)

            # Ombordan kamaytirish
            product = item_data.get('product')
            if product:
                size_obj = ProductSize.objects.filter(
                    product=product, size=item_data['size']
                ).first()
                if size_obj:
                    size_obj.quantity = max(0, size_obj.quantity - item_data['quantity'])
                    size_obj.save()

        # Mijoz statistikasini yangilash
        customer = validated_data.get('customer')
        if customer:
            customer.total_purchases += validated_data['total_amount']
            debt_amount = validated_data['total_amount'] - validated_data.get('paid_amount', 0)
            if debt_amount > 0:
                customer.total_debt += debt_amount
            customer.save()

            # Qarz yaratish (nasiya yoki to'liq to'lanmagan bo'lsa)
            paid = validated_data.get('paid_amount', 0)
            total = validated_data['total_amount']
            if paid < total:
                Debt.objects.create(
                    customer=customer,
                    sale=sale,
                    amount=total,
                    paid_amount=paid,
                    remaining_amount=total - paid,
                    status="to'lanmagan" if paid == 0 else "qisman to'langan"
                )

        return sale


# ─── Debt ─────────────────────────────────────────────────────────────────────

class DebtPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebtPayment
        fields = ['id', 'amount', 'date']
        read_only_fields = ['date']


class DebtSerializer(serializers.ModelSerializer):
    payments = DebtPaymentSerializer(many=True, read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Debt
        fields = [
            'id', 'customer', 'customer_name', 'sale',
            'amount', 'paid_amount', 'remaining_amount',
            'due_date', 'status', 'payments', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_customer_name(self, obj):
        return obj.customer.name


# ─── Expense ──────────────────────────────────────────────────────────────────

class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'category', 'description', 'amount', 'date']


# ─── Dashboard statistika ─────────────────────────────────────────────────────

class DashboardSerializer(serializers.Serializer):
    today_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    today_sales_count = serializers.IntegerField()
    month_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    month_sales_count = serializers.IntegerField()
    total_products = serializers.IntegerField()
    unique_products = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    total_debt = serializers.DecimalField(max_digits=15, decimal_places=2)
    unpaid_debts_count = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()
    recent_sales = SaleSerializer(many=True)
