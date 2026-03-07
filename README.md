# @topibolindi Referal va Sovg'a Boti

Ushbu loyiha `Aiogram 3 + PostgreSQL + Redis` asosida referal tracking, sertifikat oqimi va admin tasdiqlash jarayonini bajaradi.

## Mavjud funksiyalar

- User bot: `/start`, topshiriqlar ro'yxati, qatnashish, progress, sovg'alar, profil
- Deep-link referal: `https://t.me/<bot>?start=ref_<task_id>_<inviter_user_id>`
- Sertifikat engine: levelga yetganda yaratish, yuqori bosqichda past sertifikatni bekor qilish
- Redemption flow: `available -> pending -> approved/rejected -> used`
- Admin bot: pending so'rovlarni ko'rish, tasdiqlash/rad etish, promo-kod yaratish
- Statistik dashboard (asosiy ko'rsatkichlar)
- Audit log yozish
- FSM (Redis) bilan sertifikatdan foydalanish tasdiqlash jarayoni

## Tez ishga tushirish

1. Infrani ko'taring:

```bash
docker compose up -d
```

2. `.env.example` ni `.env` qilib to'ldiring.

3. Kutubxonalarni o'rnating:

```bash
pip install -r requirements.txt
```

4. Migratsiya:

```bash
alembic upgrade head
```

5. Botni ishga tushiring:

```bash
python -m src.main
```

## Testlar

```bash
pytest -q
```

## Arxitektura

- `src/bot/handlers/user.py` - user oqimi
- `src/bot/handlers/admin.py` - admin oqimi
- `src/services/*` - biznes logika
- `src/db/models.py` - DB modellari
- `alembic/` - migratsiyalar

## Eslatma

Anti-fraudning chuqur qoidalari (device fingerprint, behavioral scoring, manual moderation dashboard) keyingi bosqichda kengaytiriladi.
