from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from .models import User, StoreProfile


class StoreProfileInline(admin.StackedInline):
    model = StoreProfile
    can_delete = False
    fields = ['store_name', 'owner_name', 'phone']
    verbose_name = "Do'kon ma'lumotlari"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [StoreProfileInline]

    list_display = ['phone', 'get_store', 'get_owner', 'obuna_holati', 'qolgan_kun', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['phone', 'full_name', 'profile__store_name']
    ordering = ['-created_at']

    fieldsets = (
        ("Kirish ma'lumotlari", {'fields': ('phone', 'full_name', 'password')}),
        ('Obuna', {'fields': ('subscription_start', 'subscription_end')}),
        ('Holat', {'fields': ('is_active',)}),
    )

    add_fieldsets = (
        (None, {'fields': ('phone', 'full_name', 'password1', 'password2', 'subscription_end')}),
    )

    USERNAME_FIELD = 'phone'
    readonly_fields = ['created_at']

    @admin.display(description="Do'kon")
    def get_store(self, obj):
        try: return obj.profile.store_name
        except: return '-'

    @admin.display(description="Egasi")
    def get_owner(self, obj):
        try: return obj.profile.owner_name
        except: return obj.full_name or '-'

    @admin.display(description="Obuna")
    def obuna_holati(self, obj):
        if not obj.subscription_end:
            return format_html('<span style="color:gray;font-weight:bold">Yoq</span>')
        if obj.is_subscribed:
            return format_html('<span style="color:green;font-weight:bold">Faol</span>')
        return format_html('<span style="color:red;font-weight:bold">Tugagan</span>')

    @admin.display(description="Qolgan kun")
    def qolgan_kun(self, obj):
        days = obj.days_left
        if days > 60:
            return format_html('<b style="color:green">{} kun</b>', days)
        elif days > 14:
            return format_html('<b style="color:orange">{} kun</b>', days)
        elif days > 0:
            return format_html('<b style="color:red">{} kun</b>', days)
        return format_html('<b style="color:gray">0</b>')

    actions = ['obuna_1_yil', 'obuna_6_oy', 'bloklash', 'faollashtirish']

    @admin.action(description="1 yilga obuna berish")
    def obuna_1_yil(self, request, queryset):
        today = timezone.localdate()
        for user in queryset:
            if user.subscription_end and user.subscription_end > today:
                user.subscription_end += timedelta(days=365)
            else:
                user.subscription_start = today
                user.subscription_end = today + timedelta(days=365)
            user.save()
        self.message_user(request, f"{queryset.count()} ta foydalanuvchiga 1 yil obuna berildi!")

    @admin.action(description="6 oyga obuna berish")
    def obuna_6_oy(self, request, queryset):
        today = timezone.localdate()
        for user in queryset:
            if user.subscription_end and user.subscription_end > today:
                user.subscription_end += timedelta(days=182)
            else:
                user.subscription_start = today
                user.subscription_end = today + timedelta(days=182)
            user.save()
        self.message_user(request, f"{queryset.count()} ta foydalanuvchiga 6 oy obuna berildi!")

    @admin.action(description="Bloklash")
    def bloklash(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} ta foydalanuvchi bloklandi!")

    @admin.action(description="Faollashtirish")
    def faollashtirish(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} ta foydalanuvchi faollashtirildi!")


admin.site.site_header = "Dokon — Admin Panel"
admin.site.site_title = "Dokon Admin"
admin.site.index_title = "Boshqaruv Paneli"