from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Sale, SaleItem, Product, ProductSize, Customer, Debt


# ─── Sotuvni qaytarish ────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def return_sale(request, sale_id):
    """
    Sotuvni to'liq qaytarish yoki ayirboshlash.

    Body:
    {
        "reason": "Yoqmadi",           # sabab
        "return_items": [              # qaytariladigan mahsulotlar
            {"sale_item_id": 1, "quantity": 1}
        ],
        "exchange_items": [            # ayirboshlash (ixtiyoriy)
            {"product_id": 5, "size": "M", "color": "Qora", "quantity": 1, "price": 70000}
        ],
        "payment_method": "naqd"       # ayirboshlashda to'lov usuli
    }
    """
    try:
        sale = Sale.objects.get(id=sale_id, user=request.user)
    except Sale.DoesNotExist:
        return Response({'error': 'Sotuv topilmadi'}, status=status.HTTP_404_NOT_FOUND)

    if sale.is_returned:
        return Response({'error': 'Bu sotuv allaqachon qaytarilgan'}, status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason', '')
    return_items = request.data.get('return_items', [])
    exchange_items = request.data.get('exchange_items', [])
    payment_method = request.data.get('payment_method', 'naqd')

    if not return_items:
        return Response({'error': 'Qaytariladigan mahsulotlar kiritilmagan'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        returned_amount = 0

        # 1. Qaytarilgan mahsulotlarni omborga qaytarish
        for item_data in return_items:
            try:
                sale_item = SaleItem.objects.get(id=item_data['sale_item_id'], sale=sale)
            except SaleItem.DoesNotExist:
                return Response({'error': f"SaleItem {item_data['sale_item_id']} topilmadi"}, status=status.HTTP_404_NOT_FOUND)

            return_qty = int(item_data.get('quantity', sale_item.quantity))
            if return_qty > sale_item.quantity:
                return Response({'error': f"{sale_item.product_name} dan faqat {sale_item.quantity} ta bor"}, status=status.HTTP_400_BAD_REQUEST)

            # Omborga qaytarish
            if sale_item.product:
                try:
                    size_obj = ProductSize.objects.get(product=sale_item.product, size=sale_item.size)
                    size_obj.quantity += return_qty
                    size_obj.save()
                except ProductSize.DoesNotExist:
                    ProductSize.objects.create(
                        product=sale_item.product,
                        size=sale_item.size,
                        quantity=return_qty
                    )

            returned_amount += float(sale_item.price) * return_qty

            # SaleItem ni qaytarilgan deb belgilash
            sale_item.returned_quantity = return_qty
            sale_item.save()

        # 2. Eski sotuvni qaytarilgan deb belgilash
        sale.is_returned = True
        sale.return_reason = reason
        sale.returned_at = timezone.now()
        sale.returned_amount = returned_amount
        sale.save()

        # 3. Qarz bo'lsa tekshirish
        if sale.customer:
            debts = Debt.objects.filter(sale=sale, user=request.user)
            for debt in debts:
                debt.status = "to'langan"
                debt.save()

        # 4. Ayirboshlash — yangi sotuv yaratish
        exchange_sale = None
        exchange_amount = 0

        if exchange_items:
            exchange_amount = sum(
                float(i.get('price', 0)) * int(i.get('quantity', 1))
                for i in exchange_items
            )

            exchange_sale = Sale.objects.create(
                user=request.user,
                customer=sale.customer,
                total_amount=exchange_amount,
                paid_amount=exchange_amount,
                discount=0,
                payment_method=payment_method,
                note=f"Ayirboshlash: #{sale.id} sotuvdan",
            )

            for item_data in exchange_items:
                try:
                    product = Product.objects.get(id=item_data['product_id'], user=request.user)
                except Product.DoesNotExist:
                    return Response({'error': 'Mahsulot topilmadi'}, status=status.HTTP_404_NOT_FOUND)

                qty = int(item_data.get('quantity', 1))
                size = item_data.get('size', '')
                price = float(item_data.get('price', product.sell_price))

                # Ombordan kamaytirish
                try:
                    size_obj = ProductSize.objects.get(product=product, size=size)
                    if size_obj.quantity < qty:
                        return Response(
                            {'error': f"{product.name} {size} dan yetarli emas ({size_obj.quantity} ta bor)"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    size_obj.quantity -= qty
                    size_obj.save()
                except ProductSize.DoesNotExist:
                    return Response({'error': f"{product.name} {size} o'lchami topilmadi"}, status=status.HTTP_404_NOT_FOUND)

                SaleItem.objects.create(
                    sale=exchange_sale,
                    product=product,
                    product_name=product.name,
                    size=size,
                    color=item_data.get('color', ''),
                    quantity=qty,
                    price=price,
                )

        # 5. Hisob-kitob
        difference = exchange_amount - returned_amount
        # difference > 0: mijoz qo'shimcha to'laydi
        # difference < 0: dokonchi qaytarib beradi
        # difference == 0: teng

        result = {
            'success': True,
            'returned_amount': returned_amount,
            'exchange_amount': exchange_amount,
            'difference': difference,
            'difference_type': 'mijoz_toLaydi' if difference > 0 else ('dokonchi_qaytaradi' if difference < 0 else 'teng'),
            'exchange_sale_id': exchange_sale.id if exchange_sale else None,
            'message': _build_message(returned_amount, exchange_amount, difference),
        }

        return Response(result)


def _build_message(returned, exchange, diff):
    if exchange == 0:
        return f"Qaytarildi: {returned:,.0f} so'm qaytarib beriladi"
    elif diff > 0:
        return f"Ayirboshlash: Mijoz {diff:,.0f} so'm qo'shimcha to'laydi"
    elif diff < 0:
        return f"Ayirboshlash: {abs(diff):,.0f} so'm qaytarib beriladi"
    else:
        return "Ayirboshlash: To'lov farqi yo'q"


# ─── Qaytarishlar ro'yxati ────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def returns_list(request):
    sales = Sale.objects.filter(user=request.user, is_returned=True).order_by('-returned_at')
    result = []
    for s in sales:
        result.append({
            'id': s.id,
            'customer': s.customer.name if s.customer else 'Noma\'lum',
            'total_amount': float(s.total_amount),
            'returned_amount': float(s.returned_amount or 0),
            'return_reason': s.return_reason or '',
            'returned_at': s.returned_at.strftime('%d.%m.%Y %H:%M') if s.returned_at else '',
            'items': [
                {
                    'id': i.id,
                    'product_name': i.product_name,
                    'size': i.size,
                    'color': i.color,
                    'quantity': i.quantity,
                    'returned_quantity': i.returned_quantity or 0,
                    'price': float(i.price),
                }
                for i in s.items.all()
            ],
        })
    return Response(result)