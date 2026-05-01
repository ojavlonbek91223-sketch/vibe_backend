from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'customers', views.CustomerViewSet, basename='customer')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'sales', views.SaleViewSet, basename='sale')
router.register(r'debts', views.DebtViewSet, basename='debt')
router.register(r'expenses', views.ExpenseViewSet, basename='expense')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # Alohida endpointlar
    path('profile/', views.profile_view, name='profile'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('reports/', views.reports_view, name='reports'),
]

# Barcha API endpointlar:
# GET/PUT/PATCH  /api/profile/
# GET            /api/dashboard/
# GET            /api/reports/?month=2025-01
#
# GET/POST       /api/customers/
# GET/PUT/PATCH/DELETE /api/customers/{id}/
#
# GET/POST       /api/products/
# GET/PUT/PATCH/DELETE /api/products/{id}/
#
# GET/POST       /api/sales/
# GET            /api/sales/{id}/
#
# GET/POST       /api/debts/
# GET/PUT/PATCH/DELETE /api/debts/{id}/
# POST           /api/debts/{id}/pay/
#
# GET/POST       /api/expenses/
# GET/PUT/PATCH/DELETE /api/expenses/{id}/
