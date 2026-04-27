/* ══════════════════════════════════════════════════════════════
   LUXE STORE — Client-Side JavaScript
   ══════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

    // ── Flash Message Auto-Dismiss ─────────────────────────────
    const flashMessages = document.querySelectorAll('.flash-msg');
    flashMessages.forEach((msg, i) => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transform = 'translateX(30px)';
            setTimeout(() => msg.remove(), 300);
        }, 4000 + i * 500);

        msg.addEventListener('click', () => {
            msg.style.opacity = '0';
            msg.style.transform = 'translateX(30px)';
            setTimeout(() => msg.remove(), 300);
        });
    });

    // ── Mobile Nav Toggle ──────────────────────────────────────
    const navToggle = document.querySelector('.nav-toggle');
    const mobileMenu = document.querySelector('.mobile-menu');

    if (navToggle && mobileMenu) {
        navToggle.addEventListener('click', () => {
            mobileMenu.classList.toggle('active');
            const icon = navToggle.querySelector('i');
            if (mobileMenu.classList.contains('active')) {
                icon.className = 'fas fa-times';
            } else {
                icon.className = 'fas fa-bars';
            }
        });
    }

    // ── Search Suggestions ─────────────────────────────────────
    const searchInput = document.getElementById('navSearchInput');
    const searchDropdown = document.getElementById('searchDropdown');

    if (searchInput && searchDropdown) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const q = e.target.value.trim();

            if (q.length < 2) {
                searchDropdown.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                fetch(`/api/search-suggestions?q=${encodeURIComponent(q)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.length === 0) {
                            searchDropdown.classList.remove('active');
                            return;
                        }
                        searchDropdown.innerHTML = data.map(item =>
                            `<a href="/product/${item.id}" class="search-item">
                                <span>${item.name}</span>
                                <span class="search-item-price">$${item.price.toFixed(2)}</span>
                            </a>`
                        ).join('');
                        searchDropdown.classList.add('active');
                    });
            }, 300);
        });

        // Close dropdown on click outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.nav-search')) {
                searchDropdown.classList.remove('active');
            }
        });
    }

    // ── Quantity Selector ──────────────────────────────────────
    document.querySelectorAll('.quantity-selector').forEach(selector => {
        const input = selector.querySelector('input');
        const minusBtn = selector.querySelector('.qty-minus');
        const plusBtn = selector.querySelector('.qty-plus');

        if (minusBtn) {
            minusBtn.addEventListener('click', () => {
                const val = parseInt(input.value) || 1;
                if (val > 1) input.value = val - 1;
                input.dispatchEvent(new Event('change'));
            });
        }

        if (plusBtn) {
            plusBtn.addEventListener('click', () => {
                const val = parseInt(input.value) || 1;
                input.value = val + 1;
                input.dispatchEvent(new Event('change'));
            });
        }
    });

    // ── Add to Cart (AJAX) ─────────────────────────────────────
    document.querySelectorAll('.add-to-cart-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const form = btn.closest('form');
            if (!form) return;

            const formData = new FormData(form);

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Update cart badge
                    const badge = document.querySelector('.cart-badge-count');
                    if (badge) {
                        badge.textContent = data.cart_count;
                        badge.style.display = data.cart_count > 0 ? 'flex' : 'none';
                        // Pulse animation
                        badge.classList.add('pulse');
                        setTimeout(() => badge.classList.remove('pulse'), 600);
                    }
                    showToast('Added to cart!', 'success');
                }
            })
            .catch(() => {
                // Fallback: submit form normally
                form.submit();
            });
        });
    });

    // ── Cart Quantity Update (AJAX) ────────────────────────────
    document.querySelectorAll('.cart-qty-form').forEach(form => {
        const input = form.querySelector('input[name="quantity"]');
        if (input) {
            input.addEventListener('change', () => {
                const formData = new FormData(form);
                fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const subtotalEl = document.getElementById('cart-subtotal');
                        if (subtotalEl) subtotalEl.textContent = `$${data.subtotal.toFixed(2)}`;
                        const badge = document.querySelector('.cart-badge-count');
                        if (badge) badge.textContent = data.cart_count;
                    }
                })
                .catch(() => form.submit());
            });
        }
    });

    // ── Wishlist Toggle (AJAX) ─────────────────────────────────
    document.querySelectorAll('.wishlist-toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const form = btn.closest('form');
            if (!form) return;

            const formData = new FormData(form);
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const icon = btn.querySelector('i');
                    if (data.action === 'added') {
                        icon.className = 'fas fa-heart';
                        btn.classList.add('active');
                        showToast('Added to wishlist!', 'success');
                    } else {
                        icon.className = 'far fa-heart';
                        btn.classList.remove('active');
                        showToast('Removed from wishlist.', 'info');
                    }
                    const badge = document.querySelector('.wishlist-badge-count');
                    if (badge) {
                        badge.textContent = data.wishlist_count;
                        badge.style.display = data.wishlist_count > 0 ? 'flex' : 'none';
                    }
                }
            })
            .catch(() => form.submit());
        });
    });

    // ── Apply Coupon ───────────────────────────────────────────
    const couponBtn = document.getElementById('applyCouponBtn');
    if (couponBtn) {
        couponBtn.addEventListener('click', () => {
            const codeInput = document.getElementById('couponCodeInput');
            const code = codeInput.value.trim();
            if (!code) return;

            fetch('/api/apply-coupon', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ code })
            })
            .then(r => r.json())
            .then(data => {
                const discountRow = document.getElementById('discount-row');
                const discountAmount = document.getElementById('discount-amount');
                const totalEl = document.getElementById('checkout-total');
                const subtotalVal = parseFloat(document.getElementById('checkout-subtotal').dataset.value);
                const couponHidden = document.getElementById('couponCodeHidden');

                if (data.success) {
                    const discount = data.discount;
                    const discountVal = subtotalVal * (discount / 100);
                    const newTotal = subtotalVal - discountVal;

                    if (discountRow) discountRow.style.display = 'flex';
                    if (discountAmount) discountAmount.textContent = `-$${discountVal.toFixed(2)} (${discount}%)`;
                    if (totalEl) totalEl.textContent = `$${newTotal.toFixed(2)}`;
                    if (couponHidden) couponHidden.value = code;

                    showToast(`Coupon applied! ${discount}% off`, 'success');
                    couponBtn.disabled = true;
                    couponBtn.textContent = 'Applied';
                } else {
                    showToast(data.message, 'error');
                }
            });
        });
    }

    // ── Star Rating Input ──────────────────────────────────────
    const starInputs = document.querySelectorAll('.star-rating-input input');
    starInputs.forEach(input => {
        input.addEventListener('change', function() {
            const display = document.getElementById('ratingDisplay');
            if (display) display.textContent = `${this.value}/5`;
        });
    });

    // ── Modals ─────────────────────────────────────────────────
    document.querySelectorAll('[data-modal]').forEach(trigger => {
        trigger.addEventListener('click', () => {
            const modalId = trigger.dataset.modal;
            const modal = document.getElementById(modalId);
            if (modal) modal.classList.add('active');
        });
    });

    document.querySelectorAll('.modal-close, .modal-overlay').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target === el) {
                el.closest('.modal-overlay')?.classList.remove('active');
            }
        });
    });

    // Prevent closing when clicking inside modal content
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => e.stopPropagation());
    });

    // ── Edit Product Modal (Admin) ─────────────────────────────
    document.querySelectorAll('.edit-product-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const modal = document.getElementById('editProductModal');
            if (!modal) return;

            document.getElementById('editProductId').value = btn.dataset.id;
            document.getElementById('editProductName').value = btn.dataset.name;
            document.getElementById('editProductPrice').value = btn.dataset.price;
            document.getElementById('editProductDesc').value = btn.dataset.description;
            document.getElementById('editProductStock').value = btn.dataset.stock;
            document.getElementById('editProductCategory').value = btn.dataset.category;
            const featuredCheckbox = document.getElementById('editProductFeatured');
            if (featuredCheckbox) featuredCheckbox.checked = btn.dataset.featured === '1';

            const form = document.getElementById('editProductForm');
            if (form) form.action = `/admin/products/edit/${btn.dataset.id}`;

            modal.classList.add('active');
        });
    });

    // ── Edit Category Modal (Admin) ────────────────────────────
    document.querySelectorAll('.edit-category-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const modal = document.getElementById('editCategoryModal');
            if (!modal) return;

            document.getElementById('editCategoryName').value = btn.dataset.name;
            document.getElementById('editCategoryIcon').value = btn.dataset.icon;

            const form = document.getElementById('editCategoryForm');
            if (form) form.action = `/admin/categories/edit/${btn.dataset.id}`;

            modal.classList.add('active');
        });
    });

    // ── Intersection Observer for Animations ───────────────────
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });

    // ── Sort Change (Products Page) ────────────────────────────
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            const url = new URL(window.location);
            url.searchParams.set('sort', this.value);
            url.searchParams.set('page', '1');
            window.location.href = url.toString();
        });
    }

});


// ── Toast Helper ───────────────────────────────────────────────
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<i class="${icons[type] || icons.info}"></i> ${message}`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(30px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
