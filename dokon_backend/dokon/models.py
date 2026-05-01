from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import uuid


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Telefon raqami kiritilishi shart')
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'super_admin')
        extra_fields.setdefault('status', 'active')
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('user', "Do'konchi"),
        ('support', 'Support'),
        ('super_admin', 'Super Admin'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('active', 'Faol'),
        ('blocked', 'Bloklangan'),
        ('rejected', 'Rad etilgan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self):
        return f"{self.phone} ({self.get_role_display()})"

    @property
    def is_subscribed(self):
        if self.role in ('super_admin', 'support'):
            return True
        if self.status != 'active':
            return False
        if not self.subscription_end:
            return False
        return timezone.localdate() <= self.subscription_end

    @property
    def days_left(self):
        if self.role in ('super_admin', 'support'):
            return 9999
        if not self.subscription_end:
            return 0
        delta = self.subscription_end - timezone.localdate()
        return max(0, delta.days)

    @property
    def is_admin(self):
        return self.role in ('super_admin', 'support')


class StoreProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    owner_name = models.CharField(max_length=200, blank=True)
    store_name = models.CharField(max_length=200, default="Kiyim Do'koni")
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    work_hours = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=20, default="so'm")
    low_stock_alert = models.PositiveIntegerField(default=10)
    avatar = models.CharField(max_length=10, default="🏪")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.store_name} ({self.user.phone})"


class PaymentHistory(models.Model):
    PAYMENT_TYPE = [
        ('cash', 'Naqd'),
        ('card', 'Karta'),
        ('transfer', "O'tkazma"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_history')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE, default='cash')
    months_added = models.PositiveIntegerField(default=12)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    TARGET_CHOICES = [
        ('all', 'Hammasi'),
        ('active', 'Faollar'),
        ('pending', 'Kutilayotganlar'),
        ('expiring', 'Muddati tugayotganlar'),
    ]
    title = models.CharField(max_length=200)
    body = models.TextField()
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Customer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    total_purchases = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_debt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('Erkaklar kiyimi', 'Erkaklar kiyimi'),
        ('Ayollar kiyimi', 'Ayollar kiyimi'),
        ('Bolalar kiyimi', 'Bolalar kiyimi'),
        ('Poyabzal', 'Poyabzal'),
        ('Aksessuarlar', 'Aksessuarlar'),
        ('Boshqa', 'Boshqa'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    brand = models.CharField(max_length=100)
    buy_price = models.DecimalField(max_digits=15, decimal_places=2)
    sell_price = models.DecimalField(max_digits=15, decimal_places=2)
    colors = models.JSONField(default=list)
    barcode = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.brand}"

    @property
    def total_quantity(self):
        return sum(s.quantity for s in self.sizes.all())


class ProductSize(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sizes')
    size = models.CharField(max_length=10)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ['product', 'size']


class Sale(models.Model):
    PAYMENT_CHOICES = [
        ('naqd', 'Naqd'),
        ('karta', 'Karta'),
        ('nasiya', 'Nasiya'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='naqd')
    note = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    # Qaytarish maydonlari
    is_returned = models.BooleanField(default=False)
    return_reason = models.TextField(blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True)
    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Sotuv #{self.id} — {self.total_amount}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='sale_items')
    product_name = models.CharField(max_length=200)
    size = models.CharField(max_length=10)
    color = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=15, decimal_places=2)
    returned_quantity = models.PositiveIntegerField(default=0)  # Qaytarilgan miqdor

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


class Debt(models.Model):
    STATUS_CHOICES = [
        ("to'lanmagan", "To'lanmagan"),
        ("qisman to'langan", "Qisman to'langan"),
        ("to'langan", "To'langan"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='debts')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='debts')
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='debts')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="to'lanmagan")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class DebtPayment(models.Model):
    debt = models.ForeignKey(Debt, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('Ijara', 'Ijara'),
        ("Kommunal to'lovlar", "Kommunal to'lovlar"),
        ('Ish haqi', 'Ish haqi'),
        ('Transport', 'Transport'),
        ('Mahsulot xaridi', 'Mahsulot xaridi'),
        ("Ta'mirlash", "Ta'mirlash"),
        ('Marketing', 'Marketing'),
        ('Boshqa', 'Boshqa'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()

    class Meta:
        ordering = ['-date']