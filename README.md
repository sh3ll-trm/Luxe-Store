<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Stripe-Integrated-635BFF?style=for-the-badge&logo=stripe&logoColor=white" />
  <img src="https://img.shields.io/badge/PayPal-Integrated-003087?style=for-the-badge&logo=paypal&logoColor=white" />
</p>

# 💎 LUXE Store — Premium Ecommerce Platform

A full-featured, production-ready ecommerce web application built with **Flask** and **SQLite**. Features a stunning dark glassmorphism UI, complete admin dashboard, Stripe & PayPal payment integration, and everything you need for a modern online store.

---

## ✨ Features

### 🛍️ Storefront
- **Product Catalog** — Browse, filter by category, sort by price/name/date, and paginate
- **Product Detail** — Full product pages with images, descriptions, stock status, and customer reviews
- **Search** — Real-time search with AJAX-powered suggestions
- **Shopping Cart** — Add/remove items, adjust quantities, view totals
- **Wishlist** — Save products for later
- **Coupon System** — Apply discount codes at checkout
- **User Accounts** — Register, login, profile management, order history
- **Review System** — Star ratings and comments with admin moderation

### 💳 Payments
- **Stripe Integration** — Secure credit/debit card payments via Stripe Checkout
- **PayPal Integration** — PayPal button payments with client-side SDK
- **Manual / Pay Later** — Cash on delivery or bank transfer option
- **Admin-Configurable** — All API keys managed from the admin panel (no code changes needed)

### 🔧 Admin Dashboard
- **Dashboard** — Revenue, orders, products, and users at a glance
- **Product Management** — Add, edit, delete products with image upload
- **Category Management** — Organize products into categories with icons
- **Order Management** — View all orders, update status (Pending → Processing → Shipped → Delivered)
- **User Management** — View users, ban/unban accounts
- **Coupon Management** — Create, toggle, and delete discount codes
- **Review Moderation** — Approve or delete customer reviews
- **Analytics** — Revenue charts, top products, orders by status (Canvas.js charts)
- **Payment Settings** — Configure Stripe & PayPal keys, currency, and mode (sandbox/live)

### 🎨 Design
- **Dark Glassmorphism** theme with purple-to-cyan gradients
- **Fully Responsive** — Mobile, tablet, and desktop optimized
- **Micro-animations** — Smooth transitions and hover effects
- **Google Fonts** — Inter + Outfit typography
- **Font Awesome 6** icons throughout

---

## 📁 Project Structure

```
LUXE-Store/
├── app.py                          # Flask application (routes, models, logic)
├── README.md
├── requirements.txt
├── static/
│   ├── css/
│   │   └── style.css               # Complete design system
│   ├── js/
│   │   └── main.js                 # Client-side interactivity
│   └── uploads/
│       └── placeholder.png         # Default product image
└── templates/
    ├── base.html                   # Base layout (navbar, footer)
    ├── index.html                  # Homepage
    ├── products.html               # Product listing
    ├── product_detail.html         # Single product page
    ├── search_results.html         # Search results
    ├── cart.html                   # Shopping cart
    ├── wishlist.html               # Wishlist
    ├── checkout.html               # Checkout with payment selection
    ├── payment_paypal.html         # PayPal payment page
    ├── orders.html                 # Order history
    ├── login.html                  # User login
    ├── register.html               # User registration
    ├── profile.html                # User profile
    └── admin/
        ├── base.html               # Admin sidebar layout
        ├── login.html              # Admin login
        ├── dashboard.html          # Stats overview
        ├── products.html           # Product CRUD
        ├── categories.html         # Category CRUD
        ├── orders.html             # Order management
        ├── users.html              # User management
        ├── coupons.html            # Coupon management
        ├── reviews.html            # Review moderation
        ├── analytics.html          # Charts & reports
        └── settings.html           # Payment gateway config
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/sh3ll-trm/Luxe-Store
cd Luxe-Store

# Install dependencies
pip install -r requirements.txt

# Run the application
python3 app.py
```

The app will start at **http://127.0.0.1:5000**

### Default Credentials

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | `admin`  | `admin123` |

> ⚠️ **Change the admin password** after your first login in a production environment.

### Default Coupon Codes

| Code        | Discount |
|-------------|----------|
| `WELCOME10` | 10% off  |
| `SAVE20`    | 20% off  |

---

## 💳 Payment Setup

### Stripe

1. Create an account at [stripe.com](https://stripe.com)
2. Go to **Developers → API Keys** in your Stripe Dashboard
3. In the admin panel, navigate to **Settings**
4. Enable Stripe and paste your **Publishable Key** (`pk_test_...`) and **Secret Key** (`sk_test_...`)
5. Save settings

### PayPal

1. Create an account at [developer.paypal.com](https://developer.paypal.com)
2. Go to **Apps & Credentials** and create a new app
3. In the admin panel, navigate to **Settings**
4. Enable PayPal and paste your **Client ID** and **Client Secret**
5. Select **Sandbox** (testing) or **Live** (production) mode
6. Save settings

> Both gateways are optional. If neither is configured, orders will default to "Pay Later / Manual" mode.

---

## 🗄️ Database

The app uses **SQLite** — no external database setup required. The `store.db` file is auto-created on first run with the following tables:

| Table         | Description                          |
|---------------|--------------------------------------|
| `users`       | Customer accounts                    |
| `admins`      | Admin accounts                       |
| `categories`  | Product categories                   |
| `products`    | Product catalog                      |
| `cart_items`   | Shopping cart items                   |
| `wishlist`    | Saved products                       |
| `orders`      | Customer orders                      |
| `order_items` | Items within each order              |
| `reviews`     | Product reviews & ratings            |
| `coupons`     | Discount codes                       |
| `settings`    | Payment keys & app configuration     |

---

## 🛡️ Security

- Passwords hashed with **Werkzeug** (PBKDF2-SHA256)
- Session-based authentication
- Admin-only route protection via decorator
- File upload validation (type + size limit: 5MB)
- CSRF-safe form submissions
- SQL injection prevention via parameterized queries

---

## 📸 Screenshots

<details>
<summary>🏠 Homepage</summary>
<br>
Hero section with featured products, category grid, and latest arrivals.
</details>

<details>
<summary>🛒 Shopping Cart & Checkout</summary>
<br>
Cart with quantity controls, checkout with Stripe/PayPal payment selection.
</details>

<details>
<summary>📊 Admin Dashboard</summary>
<br>
Revenue stats, order overview, product management, analytics charts.
</details>

<details>
<summary>⚙️ Payment Settings</summary>
<br>
Configure Stripe & PayPal API keys directly from the admin panel.
</details>

---

## 🧰 Tech Stack

| Layer      | Technology                              |
|------------|-----------------------------------------|
| Backend    | Flask 3.x, Python 3.10+                |
| Database   | SQLite 3                                |
| Frontend   | HTML5, Vanilla CSS, Vanilla JavaScript  |
| Payments   | Stripe API, PayPal JS SDK              |
| Typography | Google Fonts (Inter, Outfit)            |
| Icons      | Font Awesome 6                          |

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

<p align="center">
  Built with ❤️ using Flask & SQLite
</p>
