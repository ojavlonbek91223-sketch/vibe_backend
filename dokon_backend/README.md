# Do'kon Backend — Django + MySQL

## Papka tuzilmasi

```
backend/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── dokon/
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── urls.py
│   └── views.py
├── .env
├── manage.py
├── requirements.txt
└── README.md
```

---

## 1. XAMPP MySQL ni ishga tushiring

XAMPP Control Panel'dan **Apache** va **MySQL** ni Start qiling.

---

## 2. MySQL'da database yarating

phpMyAdmin (http://localhost/phpmyadmin) yoki terminal orqali:

```sql
CREATE DATABASE dokon_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 3. Virtual environment yarating

```bash
cd backend
python -m venv venv
```

**Windows:**
```bash
venv\Scripts\activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

---

## 4. Kutubxonalarni o'rnating

```bash
pip install -r requirements.txt
```

> ⚠️ `mysqlclient` o'rnatishda xatolik bo'lsa, avval:
> - **Windows:** `pip install mysqlclient` (yoki binary: https://www.lfd.uci.edu/~gohlke/pythonlibs/#mysqlclient)
> - **Mac:** `brew install mysql-client` keyin `pip install mysqlclient`

---

## 5. .env faylini sozlang

`.env` faylini oching va ma'lumotlarni kiriting:

```env
DEBUG=True
SECRET_KEY=django-insecure-your-very-secret-key-here

DB_NAME=dokon_db
DB_USER=root
DB_PASSWORD=        # XAMPP default: bo'sh
DB_HOST=127.0.0.1
DB_PORT=3306
```

---

## 6. Migration va server

```bash
# Migratsiyalarni yarating
python manage.py makemigrations

# Migratsiyalarni ishga tushiring (jadvallar yaratiladi)
python manage.py migrate

# Admin foydalanuvchi yarating
python manage.py createsuperuser

# Serverni ishga tushiring
python manage.py runserver
```

Server: **http://127.0.0.1:8000**

---

## 7. Frontend .env

Frontend papkasida `.env` fayl yarating:

```env
VITE_API_URL=http://127.0.0.1:8000/api
```

---

## API Endpointlar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET/PUT | `/api/profile/` | Do'kon profili |
| GET | `/api/dashboard/` | Bosh sahifa statistika |
| GET | `/api/reports/?month=2025-01` | Hisobotlar |
| GET/POST | `/api/customers/` | Mijozlar ro'yxati |
| GET/PUT/DELETE | `/api/customers/{id}/` | Mijoz |
| GET/POST | `/api/products/` | Mahsulotlar ro'yxati |
| GET/PUT/DELETE | `/api/products/{id}/` | Mahsulot |
| GET/POST | `/api/sales/` | Sotuvlar |
| GET | `/api/sales/{id}/` | Sotuv |
| GET/POST | `/api/debts/` | Qarzlar |
| POST | `/api/debts/{id}/pay/` | Qarzga to'lov |
| GET/POST | `/api/expenses/` | Xarajatlar |
| GET/PUT/DELETE | `/api/expenses/{id}/` | Xarajat |

### Query parametrlar

```
GET /api/products/?search=ko'ylak&category=Erkaklar kiyimi
GET /api/sales/?month=2025-01&search=Jamshid
GET /api/debts/?status=unpaid        # unpaid | partial | paid | all
GET /api/expenses/?month=2025-01&category=Ijara
```

---

## Admin panel

**http://127.0.0.1:8000/admin/** — Django admin paneli (barcha ma'lumotlarni ko'rish va tahrirlash)

---

## Frontend bilan ulash (storage.ts o'rniga)

Frontend'da `src/app/utils/api.ts` fayl yarating:

```typescript
const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export const api = {
  get: (url: string) => fetch(`${BASE}${url}`).then(r => r.json()),
  post: (url: string, data: any) => fetch(`${BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json()),
  put: (url: string, data: any) => fetch(`${BASE}${url}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json()),
  patch: (url: string, data: any) => fetch(`${BASE}${url}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json()),
  delete: (url: string) => fetch(`${BASE}${url}`, { method: 'DELETE' }),
};
```
