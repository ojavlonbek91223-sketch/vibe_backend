from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from dokon.views import (
    profile_view, dashboard_view,
    CustomerViewSet, ProductViewSet, SaleViewSet,
    DebtViewSet, ExpenseViewSet, reports_view,
)
from dokon.auth_views import (
    register_view, login_view, me_view, change_password_view,
)
from dokon.admin_views import (
    admin_login_view, admin_dashboard, admin_users_list,
    admin_user_detail, admin_approve_user, admin_reject_user,
    admin_add_subscription, admin_notifications,
    admin_list, admin_create, admin_manage,
)
from dokon.return_views import return_sale, returns_list

router = DefaultRouter()
router.register('customers', CustomerViewSet, basename='customer')
router.register('products', ProductViewSet, basename='product')
router.register('sales', SaleViewSet, basename='sale')
router.register('debts', DebtViewSet, basename='debt')
router.register('expenses', ExpenseViewSet, basename='expense')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        # Auth
        path('auth/register/', register_view),
        path('auth/login/', login_view),
        path('auth/me/', me_view),
        path('auth/change-password/', change_password_view),
        path('auth/refresh/', TokenRefreshView.as_view()),

        # Admin panel
        path('admin-panel/login/', admin_login_view),
        path('admin-panel/dashboard/', admin_dashboard),
        path('admin-panel/users/', admin_users_list),
        path('admin-panel/users/<str:user_id>/', admin_user_detail),
        path('admin-panel/users/<str:user_id>/approve/', admin_approve_user),
        path('admin-panel/users/<str:user_id>/reject/', admin_reject_user),
        path('admin-panel/users/<str:user_id>/subscription/', admin_add_subscription),
        path('admin-panel/notifications/', admin_notifications),
        path('admin-panel/admins/', admin_list),
        path('admin-panel/admins/create/', admin_create),
        path('admin-panel/admins/<str:admin_id>/', admin_manage),

        # Qaytarish
        path('sales/<int:sale_id>/return/', return_sale),
        path('returns/', returns_list),

        # App
        path('profile/', profile_view),
        path('dashboard/', dashboard_view),
        path('reports/', reports_view),
        path('', include(router.urls)),
    ])),
]