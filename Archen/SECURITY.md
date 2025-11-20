# سیاست دسترسی و امنیت در Archen

این سند خلاصه‌ای از سیاست فعلی دسترسی (Access Control) و نقاط عمومی/حساس پروژه را توضیح می‌دهد تا در توسعه‌های بعدی به‌صورت ناخواسته حفره‌ای مشابه ایجاد نشود.

## ۱. احراز هویت و نقش‌ها

- سیستم بر پایه‌ی احراز هویت Django و مدل کاربر `users.CustomUser` کار می‌کند.
- ورود از طریق مسیر `GET /users/login/` انجام می‌شود.
- خروج از طریق `POST/GET /users/logout/` انجام می‌شود.
- نقش‌ها (`role`) در مدل کاربر نگهداری می‌شود و در بعضی ویوها (مثل `jobs` و `production_line`) برای محدود کردن دسترسی استفاده می‌شوند.

## ۲. صفحه‌ها و APIهای عمومی

فقط مسیرهای زیر بدون لاگین در دسترس هستند (عمداً عمومی):

- صفحه ورود: `GET /users/login/`
- صفحه عمومی وضعیت سفارش برای دارنده‌ی QR:
  - `GET /orders/public/<serial>/`
- تصویر QR:
  - `GET /orders/qr/<code>.svg`
  - اگر `code` یک URL نباشد، به‌صورت خودکار به لینک عمومی سفارش تبدیل می‌شود:
    - `reverse('orders:public_order_summary', args=[code])`
    - و سپس با `request.build_absolute_uri` به آدرس کامل (مثلاً `https://archenmobl.com/orders/public/<serial>/`) تبدیل می‌شود.
- مسیرهای PWA (مانند manifest، service worker و offline) که فقط محتوای استاتیک/عمومی دارند.

هر مسیر جدیدی که **عمداً** باید بدون لاگین در دسترس باشد باید در این بخش ثبت شود.

## ۳. مسیرهای محافظت‌شده (نیازمند لاگین)

تمام صفحات مدیریتی، فرم‌ها و گزارش‌ها نیاز به لاگین دارند:

- **داشبورد اصلی**  
  - `GET /` و `GET /dashboard/` → ویوی `dashboard_view` با `@login_required`.

- **سفارش‌ها (`orders`)** — همگی با `LoginRequiredMixin` یا `@login_required` محافظت شده‌اند:
  - لیست، ایجاد، ویرایش، حذف دسته‌ای، تغییر مرحله، فید زنده:
    - `/orders/`, `/orders/create/`, `/orders/edit/<pk>/`, `/orders/bulk-delete/`,
      `/orders/products-by-models/`, `/orders/jobs-by-selection/`,
      `/orders/stage/<pk>/`, `/orders/api/live-orders/`
  - چاپ کارت گارانتی و لیبل:
    - `/orders/warranty/`, `/orders/warranty/s/<serial>/`, `/orders/label/<pk>/`

- **گزارش‌ها (`reports`)** — همگی با `@login_required(login_url="/users/login/")`:
  - داشبورد و متریک‌ها:
    - `/reports/`, `/reports/api/metrics/`, `/reports/scrap/`
  - گزارش‌های کارها:
    - `/reports/jobs/`, `/reports/jobs/<job_number>/`, `/reports/jobs_list/`
  - پنل‌ها و خروجی‌ها:
    - `/reports/job-details/`, `/reports/job-details/<job_number>/export/<fmt>/`
    - `/reports/order-details/`, `/reports/order-details/<order_id>/export/<fmt>/`
    - `/reports/log-details/`, `/reports/log-details/<log_id>/export/<fmt>/`
    - `/reports/logs/export/<fmt>/`

- **موجودی (`inventory`)**، **خط تولید (`production_line`)**، **کارها (`jobs`)**،  
  **نگه‌داری (`maintenance`)**، **حسابداری (`accounting`)** و **مدیریت کاربران (`users`)**  
  همگی برای تمام ویوهای خود از `@login_required` (و در برخی موارد `user_passes_test`) استفاده می‌کنند.

هر ویوی جدید در این اپ‌ها باید **به‌صورت پیش‌فرض** لاگین‌دار تعریف شود، مگر آن‌که عمداً عمومی طراحی شده باشد.

## ۴. اصول توسعه‌ی امن

هنگام اضافه‌کردن ویو/صفحه‌ی جدید:

1. اگر ویو مدیریتی است (سفارش، تولید، گزارش، موجودی، حسابداری و…):
   - حتماً یکی از این دو الگو را استفاده کنید:
     - `@login_required(login_url="/users/login/")` برای ویوهای تابعی.
     - `LoginRequiredMixin` برای کلاس‌های مبتنی بر CBV.
2. اگر ویو عمومی است (بدون لاگین):
   - آن را در بخش «مسیرهای عمومی» در همین فایل مستند کنید.
   - مطمئن شوید داده‌هایی که نشان می‌دهد از نظر حریم خصوصی و کسب‌وکار قابل‌قبول است
     (مثل صفحه‌ی عمومی وضعیت سفارش که مخصوص دارنده‌ی کارت گارانتی است).
3. از استفاده‌ی مستقیم از مسیرهایی مثل `/orders/`، `/reports/`، `/inventory/` بدون لاگین خودداری کنید؛
   همیشه روی محیط تست/سرور با یک مرورگر بدون لاگین، مسیرهای جدید را امتحان کنید تا مطمئن شوید به صفحه‌ی لاگین هدایت می‌شوند.

این فایل باید همراه با هر تغییر بزرگ در سیستم احراز هویت/دسترسی یا اضافه‌شدن مسیر عمومی جدید به‌روزرسانی شود.

