# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Login, subscription and session-timeout screens."""
from datetime import datetime
from typing import Dict
from typing import Optional
import json
import streamlit as st
import time

from cdss.common.log import logger
import cdss.security.auth_service as _AUTH
from cdss.security.passwords import (
    verify_password,
)


# =========================================================
# الثوابت
# =========================================================
SESSION_TIMEOUT = 30 * 60

# =========================================================
# تحميل المشتركين
# =========================================================
def load_subscribers() -> Dict[str, str]:
    try:
        raw  = st.secrets.get("subscribers_json") or st.secrets.get("subscribers", "{}")
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        return {str(k).strip().lower(): str(v).strip() for k, v in data.items()}
    except Exception:
        return {}

# ── Vendor identity — configurable for resale ───────────────────────────────
# Support phone and e-mail were hard-coded in four places. Every lab that buys
# this build shipped with the original developer's personal mobile number and
# private Gmail address on the login page, the renewal banner and the expiry
# logout message. Override per deployment in .streamlit/secrets.toml:
#
#   vendor_name  = "Orange Lab"
#   vendor_phone = "+20 …"
#   vendor_email = "support@…"
def _vendor(key: str, default: str) -> str:
    try:
        return str(st.secrets.get(key, default) or default)
    except Exception:
        return default

# Nothing here touches st.secrets at IMPORT time. In the single-file app these
# four values were read after st.set_page_config(); as module globals they would
# be read while the page module is still being imported -- before
# set_page_config -- and Streamlit reports a missing secrets file with st.error,
# which must not be the first Streamlit call of a run. refresh_secrets() fills
# them in, and main() calls it right after the page is configured.
_DEFAULT_VENDOR_PHONE = "01016872801"
_DEFAULT_VENDOR_EMAIL = "Hussein.ali77121@gmail.com"

VENDOR_PHONE = _DEFAULT_VENDOR_PHONE

VENDOR_EMAIL = _DEFAULT_VENDOR_EMAIL

SUBSCRIBERS: Dict[str, str] = {}

def load_subscriber_hashes() -> Dict[str, str]:
    try:
        raw = st.secrets.get("subscriber_hashes", "{}")
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        return {str(k).strip().lower(): str(v).strip() for k, v in data.items()}
    except Exception:
        return {}

SUBSCRIBER_HASHES: Dict[str, str] = {}


def refresh_secrets() -> None:
    """Read subscribers, password hashes and vendor contact from st.secrets.

    Called by main() on every script run, after st.set_page_config() -- exactly
    when the single-file app read them, so an edited secrets file takes effect
    on the next click.
    """
    global VENDOR_PHONE, VENDOR_EMAIL, SUBSCRIBERS, SUBSCRIBER_HASHES
    VENDOR_PHONE = _vendor("vendor_phone", _DEFAULT_VENDOR_PHONE)
    VENDOR_EMAIL = _vendor("vendor_email", _DEFAULT_VENDOR_EMAIL)
    SUBSCRIBERS = load_subscribers()
    SUBSCRIBER_HASHES = load_subscriber_hashes()

# =========================================================
# اكتشاف اسم المريض من OCR
# =========================================================

def get_subscription_days_left(email: str) -> Optional[int]:
    email = (email or "").strip().lower()
    if email not in SUBSCRIBERS:
        return None
    expiry_str = SUBSCRIBERS[email]
    try:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today       = datetime.now().date()
        return (expiry_date - today).days
    except Exception:
        return None

def show_login_page():
    if st.session_state.get("logout_reason"):
        st.warning(st.session_state.pop("logout_reason"))
    st.markdown("""
    <div style='text-align:center; padding: 3rem 0 1rem 0'>
        <span style='font-size:3rem'>🍊</span>
        <h2 style='margin:0.3rem 0 0.1rem 0'>Microbiology CDSS</h2>
        <p style='color:gray; margin:0'>AI-Assisted Antibiotic Decision Support -- Egyptian Market</p>
    </div>
    """, unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("#### 🔐 تسجيل الدخول")
        email    = st.text_input("📧 البريد الإلكتروني", placeholder="example@hospital.com",
                                 label_visibility="collapsed")
        password = st.text_input("🔑 كلمة المرور", type="password",
                                 placeholder="كلمة المرور",
                                 label_visibility="collapsed")
        login_btn = st.button("دخول", use_container_width=True, type="primary")
        if login_btn:
            return email.strip().lower(), password
        st.markdown("---")
        st.markdown(f"""
        <div style='text-align:center; border:1px solid #E8A33D; border-radius:10px;
                    padding:14px 12px; background:rgba(232,163,61,0.07)'>
          <div style='font-size:1.02rem; font-weight:700; color:#C2410C;
                      margin-bottom:6px'>
            ⏳ الفترة التجريبية المجانية تقترب من نهايتها
          </div>
          <div style='font-size:0.9rem; line-height:1.85'>
            برجاء سرعة التواصل معنا لتسجيل اشتراكك قبل انتهاء المدة، حفاظًا على
            استمرار عملك دون انقطاع والاحتفاظ ببياناتك وإعداداتك.<br>
            <span style='color:#B45309; font-weight:600'>
              بعد انتهاء الفترة التجريبية يتوقف الدخول إلى النظام تلقائيًا.
            </span>
          </div>
          <div style='margin:12px 0 8px; font-size:1.05rem; font-weight:700'>
            📞 <a href='tel:{VENDOR_PHONE}' style='text-decoration:none'>{VENDOR_PHONE}</a>
            &nbsp;·&nbsp;
            ✉️ <a href='mailto:{VENDOR_EMAIL}' style='text-decoration:none'>{VENDOR_EMAIL}</a>
          </div>
          <div style='font-size:0.88rem; color:#555; line-height:1.8'>
            🔹 تجريبي مجاني: <b>15 يوم</b><br>
            🔹 شهري: <b>200 جنيه</b><br>
            🔹 سنوي: <b>2000 جنيه</b>
            <span style='color:#15803D; font-weight:600'>(توفير 400 جنيه)</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
    return None

def check_subscription(email: str, password: str = "") -> bool:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        st.warning("⚠️ أدخل بريدًا إلكترونيًا صحيحًا")
        return False
    # ── Throttle ─────────────────────────────────────────────────────────────
    # 2026-08-01 this counter lived in st.session_state, which is per BROWSER
    # SESSION: an attacker clearing cookies, opening a private window, or
    # driving the app from a script got a fresh five attempts every time. It
    # stopped a naive loop and nothing else.
    #
    # 2026-08-03 it moved to auth_service.py, keyed by ACCOUNT and persisted on
    # disk, so the limit follows the e-mail rather than the browser. Storage
    # failures FAIL OPEN and are logged loudly — a laboratory locked out of its
    # own CDSS because a disk filled up is a worse outcome than a slower brute
    # force, and the attempt is recorded either way.
    #
    # Still NOT a distributed rate limiter: one JSON file under one process. If
    # this is ever scaled horizontally the store must move to Redis, and the
    # interface in auth_service is deliberately the shape that migration keeps.
    _locked, _wait, _prior_fails = _AUTH.check_lockout(email)
    if _locked:
        st.error(f"⛔ محاولات كثيرة خاطئة على هذا الحساب. "
                 f"حاول بعد {_wait // 60}:{_wait % 60:02d} دقيقة.")
        return False
    if email not in SUBSCRIBERS:
        st.error("❌ هذا البريد غير مسجل في النظام")
        st.info(
            "**للحصول على نسخة تجريبية مجانية (15 يوم) أو اشتراك:**\n\n"
            f"📞 {VENDOR_PHONE}\n\n✉️ {VENDOR_EMAIL}\n\n---\n"
            "🔹 تجريبي: **مجاناً - 15 يوم**\n"
            "🔹 شهري: **200 جنيه**\n"
            "🔹 سنوي: **2000 جنيه** *(توفير 400 ج)*"
        )
        return False
    _stored = SUBSCRIBER_HASHES.get(email)
    if _stored:
        if not verify_password(password, _stored):
            _now_locked, _wait2, _left = _AUTH.record_failure(email, "bad password")
            if _now_locked:
                st.error(f"⛔ تم قفل المحاولات {_wait2 // 60} دقائق "
                         f"بعد {_AUTH.MAX_ATTEMPTS} محاولات خاطئة.")
            else:
                st.error(f"❌ كلمة المرور غير صحيحة ({_left} محاولة متبقية)")
            return False
    elif SUBSCRIBER_HASHES:
        # FIX 2026-08-01: this branch printed a warning and then FELL THROUGH,
        # returning True. The comment beneath it said "do not silently accept a
        # bare email while the rest of the estate is protected" -- which is
        # exactly what the code then did, minus the silence. Any account added
        # to `subscribers` without a matching entry in `subscriber_hashes` was a
        # password-free door into a paid product, and adding a subscriber
        # without a hash is the easy mistake to make.
        # Fail closed: once ANY account is protected, an unprotected one cannot
        # log in at all.
        st.error(
            "⛔ هذا الحساب غير مفعّل بكلمة مرور، والنظام يعمل بوضع "
            "الحماية الكاملة.\n\n"
            f"تواصل مع الدعم لتفعيله: 📞 {VENDOR_PHONE} | ✉️ {VENDOR_EMAIL}"
        )
        logger.error("login refused: %s exists in `subscribers` but has no "
                     "entry in `subscriber_hashes` while %d other account(s) "
                     "do. Add a hash for it with make_password_hash().",
                     email, len(SUBSCRIBER_HASHES))
        return False

    days_left = get_subscription_days_left(email)
    if days_left is None:
        st.error("خطأ في بيانات الاشتراك، تواصل مع الدعم")
        return False
    st.session_state.email     = email
    st.session_state.days_left = days_left
    # Credentials accepted: clear the account's counter and record the sign-in.
    _AUTH.record_success(email)
    if days_left < 0:
        st.error(f"⏳ انتهى اشتراكك منذ {abs(days_left)} يوم")
        st.info(f"📞 للتجديد: {VENDOR_PHONE} | ✉️ {VENDOR_EMAIL}")
        return False
    if days_left <= 3:
        st.warning(f"⚠️ اشتراكك ينتهي خلال **{days_left} يوم فقط**")
    elif days_left <= 7:
        st.info(f"ℹ️ متبقي **{days_left} أيام** على انتهاء الاشتراك")
    else:
        st.success(f"✅ أهلاً بك! الاشتراك ساري -- متبقي {days_left} يومًا")
    return True

def logout(reason: str = "تم تسجيل الخروج.") -> None:
    st.session_state.clear()
    st.session_state["logout_reason"] = reason
    st.rerun()

def handle_session_timeout() -> None:
    last_activity = st.session_state.get("last_activity")
    if last_activity:
        elapsed = time.time() - last_activity
        if elapsed > SESSION_TIMEOUT:
            logout("انتهت صلاحية الجلسة بسبب عدم النشاط. الرجاء تسجيل الدخول مرة أخرى.")
    st.session_state.last_activity = time.time()

def render_top_bar() -> None:
    left, right = st.columns([6, 1])
    with left:
        days = get_subscription_days_left(st.session_state.get("email", ""))
        st.session_state.days_left = days
        if days is None:
            # The account disappeared from the subscriber table mid-session
            # (revoked, refunded, typo-fixed). Access must stop immediately.
            logout("تم إنهاء الجلسة: الحساب لم يعد مسجلاً.")
        elif days < 0:
            # check_subscription() only runs at LOGIN. Without this branch an
            # expired subscription kept full access until the 30-minute idle
            # timeout happened to fire.
            logout(f"⏳ انتهى اشتراكك منذ {abs(days)} يوم. للتجديد: {VENDOR_PHONE}")
        if days is not None:
            if days <= 3:
                st.warning(
                    f"⚠️ اشتراك **{st.session_state.email}** سينتهي خلال **{days} يوم(أيام)** -- يُرجى التجديد قريبًا."
                )
            else:
                st.info(f"✅ اشتراك **{st.session_state.email}** سارٍ -- متبقي **{days}** يومًا.")
    with right:
        if st.button("تسجيل خروج", use_container_width=True):
            logout("تم تسجيل الخروج بنجاح.")
