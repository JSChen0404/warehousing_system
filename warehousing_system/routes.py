import os
import msal
import functools
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from flask_wtf.csrf import generate_csrf
from warehousing_system.forms import (SearchForm, PackingListForm, UpdateQuantityForm,
                                       WithdrawalForm, ApprovalForm)
from warehousing_system.models import (User, PackingList, Inventory, ProductCatalog,
                                        Withdrawal, Approval)
from warehousing_system import db
from datetime import datetime
from sqlalchemy import or_

pages = Blueprint("pages", __name__, template_folder="templates", static_folder="static")


# ─── helpers ────────────────────────────────────────────────────
def _get_inventory(code, batch):
    """用複合主鍵查詢庫存"""
    return Inventory.query.filter_by(
        child_item_code=code, batch_or_serial_no=batch
    ).first()


def _msal_app():
    cid = os.environ.get("AZURE_CLIENT_ID")
    csec = os.environ.get("AZURE_CLIENT_SECRET")
    if not cid or not csec:
        raise RuntimeError("Missing AZURE_CLIENT_ID / AZURE_CLIENT_SECRET")
    return msal.ConfidentialClientApplication(
        client_id=cid,
        authority="https://login.microsoftonline.com/common",
        client_credential=csec,
    )

def _build_auth_url():
    redirect_uri = url_for("pages.auth_callback", _external=True)
    flow = _msal_app().initiate_auth_code_flow(
        scopes=["User.Read"], redirect_uri=redirect_uri
    )
    session["auth_flow"] = flow
    return flow["auth_uri"]

def login_required(route):
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        if not session.get("email"):
            return redirect(url_for("pages.login"))
        return route(*args, **kwargs)
    return wrapper

def approver_required(route):
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        if not session.get("email"):
            return redirect(url_for("pages.login"))
        user = User.query.filter_by(email=session.get("email")).first()
        if not user or not user.is_approver:
            flash("您沒有審核權限", "danger")
            return redirect(url_for("pages.index"))
        return route(*args, **kwargs)
    return wrapper


# ─── Auth routes ────────────────────────────────────────────────
@pages.route("/")
@login_required
def index():
    return redirect(url_for(".search"))

@pages.route("/login", methods=["GET"])
def login():
    if session.get("email"):
        return redirect(url_for(".search"))
    return render_template("login.html", title="Login", form=None)

@pages.route("/login/microsoft", methods=["GET"])
def login_microsoft():
    if session.get("email"):
        return redirect(url_for(".search"))
    return redirect(_build_auth_url())

@pages.route("/getAToken", methods=["GET"])
def auth_callback():
    flow = session.get("auth_flow")
    if not flow:
        flash("Login session expired. Please try again.", "danger")
        return redirect(url_for(".login"))
    result = _msal_app().acquire_token_by_auth_code_flow(flow, request.args)
    if "id_token_claims" not in result:
        flash("Microsoft login failed.", "danger")
        return redirect(url_for(".login"))
    claims = result["id_token_claims"]
    email = (claims.get("preferred_username") or claims.get("upn")
             or claims.get("email") or "").lower()
    session["email"] = email
    session["azure_oid"] = claims.get("oid")
    session["name"] = claims.get("name")
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, password="oauth_user")
        db.session.add(user)
        db.session.commit()
    session["is_approver"] = user.is_approver
    flash("Login successful.", "success")
    return redirect(url_for(".search"))

@pages.route("/logout", methods=["GET"])
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for(".login"))


# ─── API：產品目錄 ─────────────────────────────────────────────
@pages.route("/api/parent_item_names", methods=["GET"])
@login_required
def get_parent_item_names():
    names = db.session.query(ProductCatalog.parent_item_name).distinct().all()
    return jsonify([n[0] for n in names])

@pages.route("/api/children_by_parent/<parent_item_name>", methods=["GET"])
@login_required
def get_children_by_parent(parent_item_name):
    items = ProductCatalog.query.filter_by(parent_item_name=parent_item_name).all()
    return jsonify([{'id': i.id, 'child_item_name': i.child_item_name} for i in items])


# ─── 新增資料（兩步驟）─────────────────────────────────────────
@pages.route("/add", methods=["GET", "POST"])
@login_required
def add_data():
    """Step 1: 填寫貨物層級資料"""
    form = PackingListForm()
    names = (db.session.query(ProductCatalog.parent_item_name)
             .distinct().order_by(ProductCatalog.parent_item_name).all())
    form.parent_item_name.choices = [('', '-- 請選擇貨物名稱 --')] + [(n[0], n[0]) for n in names]

    if form.validate_on_submit():
        session['add_data'] = {
            'parent_item_name': form.parent_item_name.data,
            'experiment_category': form.experiment_category.data,
            'arrival_date': form.arrival_date.data.isoformat(),
            'packing_no': form.packing_no.data,
            'purchase_order_no': form.purchase_order_no.data,
            'parent_item_code': form.parent_item_code.data,
        }
        return redirect(url_for(".add_items"))

    return render_template("add_data.html", title="新增資料", form=form)


@pages.route("/add/items", methods=["GET", "POST"])
@login_required
def add_items():
    """Step 2: 填寫每個 child item 的明細（每個品項可多批號）"""
    data = session.get('add_data')
    if not data:
        flash("請先填寫貨物資料", "warning")
        return redirect(url_for(".add_data"))

    items = (ProductCatalog.query
             .filter_by(parent_item_name=data['parent_item_name'])
             .order_by(ProductCatalog.id).all())

    if not items:
        flash("此貨物名稱下沒有品項", "danger")
        return redirect(url_for(".add_data"))

    if request.method == 'POST':
        try:
            packing = PackingList.query.filter_by(packing_no=data['packing_no']).first()
            if not packing:
                packing = PackingList(
                    packing_no=data['packing_no'],
                    arrival_date=datetime.strptime(data['arrival_date'], '%Y-%m-%d').date(),
                    purchase_order_no=data.get('purchase_order_no'),
                    parent_item_name=data['parent_item_name'],
                    experiment_category=data.get('experiment_category'),
                    parent_item_code=data.get('parent_item_code'),
                )
                db.session.add(packing)

            child_item_codes = request.form.getlist('child_item_code[]')
            child_item_names = request.form.getlist('child_item_name[]')
            batch_nos = request.form.getlist('batch_or_serial_no[]')
            exp_dates = request.form.getlist('expiration_date[]')
            quantities = request.form.getlist('quantity[]')
            units = request.form.getlist('unit[]')
            test_qtys = request.form.getlist('test_quantity[]')
            temps = request.form.getlist('storage_temperature_c[]')
            locations = request.form.getlist('storage_location[]')
            toxics = request.form.getlist('has_toxic_chemical[]')

            count = 0
            for i in range(len(child_item_names)):
                if not child_item_codes[i] or not batch_nos[i] or not quantities[i]:
                    continue

                # 檢查複合主鍵是否已存在
                existing = _get_inventory(child_item_codes[i], batch_nos[i])
                if existing:
                    flash(f"品項 {child_item_codes[i]} + 批號 {batch_nos[i]} 已存在，已跳過", "warning")
                    continue

                inv = Inventory(
                    child_item_code=child_item_codes[i],
                    batch_or_serial_no=batch_nos[i],
                    packing_no=data['packing_no'],
                    child_item_name=child_item_names[i],
                    expiration_date=(datetime.strptime(exp_dates[i], '%Y-%m-%d').date()
                                   if exp_dates[i] else None),
                    quantity=float(quantities[i]),
                    unit=units[i],
                    test_quantity=int(test_qtys[i]) if test_qtys[i] else 0,
                    storage_temperature_c=float(temps[i]) if temps[i] else None,
                    storage_location=locations[i] if locations[i] else None,
                    has_toxic_chemical=(str(i) in toxics),
                    received_by=session.get('name'),
                )
                db.session.add(inv)
                count += 1

            db.session.commit()
            session.pop('add_data', None)
            flash(f"成功新增 {count} 個品項", "success")
            return redirect(url_for(".inventory"))

        except Exception as e:
            db.session.rollback()
            flash(f"新增失敗：{str(e)}", "danger")

    return render_template(
        "add_items.html", title="填寫品項明細",
        data=data, items=items, csrf_token=generate_csrf()
    )


# ─── 庫存總覽 ──────────────────────────────────────────────────
@pages.route("/inventory", methods=["GET"])
@login_required
def inventory():
    page = request.args.get('page', 1, type=int)
    per_page = 50

    pagination = db.session.query(
        Inventory, PackingList
    ).join(
        PackingList, Inventory.packing_no == PackingList.packing_no
    ).order_by(
        PackingList.arrival_date.desc(),
        Inventory.child_item_code,
        Inventory.batch_or_serial_no
    ).paginate(page=page, per_page=per_page, error_out=False)

    inventory_data = []
    for inv, pack in pagination.items:
        inventory_data.append({
            'child_item_code': inv.child_item_code,
            'batch_or_serial_no': inv.batch_or_serial_no,
            'packing_no': inv.packing_no,
            'arrival_date': pack.arrival_date,
            'purchase_order_no': pack.purchase_order_no,
            'parent_item_name': pack.parent_item_name,
            'experiment_category': pack.experiment_category,
            'parent_item_code': pack.parent_item_code,
            'child_item_name': inv.child_item_name,
            'expiration_date': inv.expiration_date,
            'quantity': float(inv.quantity) if inv.quantity else 0,
            'unit': inv.unit,
            'test_quantity': inv.test_quantity,
            'storage_temperature_c': inv.storage_temperature_c,
            'storage_location': inv.storage_location,
            'has_toxic_chemical': inv.has_toxic_chemical,
            'received_by': inv.received_by,
            'issue_date': inv.issue_date,
        })

    return render_template(
        "inventory.html", title="庫存總覽",
        inventories=inventory_data, pagination=pagination
    )


# ─── 搜尋 ──────────────────────────────────────────────────────
@pages.route("/search", methods=["GET", "POST"])
@login_required
def search():
    form = SearchForm()
    results = []
    page = request.args.get('page', 1, type=int)
    per_page = 50
    pagination = None

    if form.validate_on_submit():
        query = db.session.query(
            Inventory, PackingList
        ).join(
            PackingList, Inventory.packing_no == PackingList.packing_no
        )

        conditions = []
        if form.packing_no.data:
            conditions.append(Inventory.packing_no.ilike(f"%{form.packing_no.data}%"))
        if form.purchase_order_no.data:
            conditions.append(PackingList.purchase_order_no.ilike(f"%{form.purchase_order_no.data}%"))
        if form.parent_item_name.data:
            conditions.append(PackingList.parent_item_name.ilike(f"%{form.parent_item_name.data}%"))
        if form.child_item_name.data:
            conditions.append(Inventory.child_item_name.ilike(f"%{form.child_item_name.data}%"))
        if form.child_item_code.data:
            conditions.append(Inventory.child_item_code.ilike(f"%{form.child_item_code.data}%"))
        if form.batch_or_serial_no.data:
            conditions.append(Inventory.batch_or_serial_no.ilike(f"%{form.batch_or_serial_no.data}%"))

        if conditions:
            query = query.filter(or_(*conditions))
            pagination = query.order_by(
                PackingList.arrival_date.desc(),
                Inventory.child_item_code,
                Inventory.batch_or_serial_no
            ).paginate(page=page, per_page=per_page, error_out=False)

            for inv, pack in pagination.items:
                results.append({
                    'child_item_code': inv.child_item_code,
                    'batch_or_serial_no': inv.batch_or_serial_no,
                    'packing_no': inv.packing_no,
                    'arrival_date': pack.arrival_date,
                    'purchase_order_no': pack.purchase_order_no,
                    'parent_item_name': pack.parent_item_name,
                    'experiment_category': pack.experiment_category,
                    'parent_item_code': pack.parent_item_code,
                    'child_item_name': inv.child_item_name,
                    'expiration_date': inv.expiration_date,
                    'quantity': float(inv.quantity) if inv.quantity else 0,
                    'unit': inv.unit,
                    'test_quantity': inv.test_quantity,
                    'storage_temperature_c': inv.storage_temperature_c,
                    'storage_location': inv.storage_location,
                    'has_toxic_chemical': inv.has_toxic_chemical,
                    'received_by': inv.received_by,
                    'issue_date': inv.issue_date,
                })
            if not results:
                flash("查無相關資料", "danger")
        else:
            flash("請至少填寫一個搜尋條件", "warning")

    return render_template(
        "search.html", title="搜尋資料",
        form=form, results=results, pagination=pagination
    )


# ─── 更新資料 ──────────────────────────────────────────────────
@pages.route("/update", methods=["GET", "POST"])
@login_required
def update_data():
    form = UpdateQuantityForm()
    results = []

    if request.method == 'POST' and 'search' in request.form:
        if form.validate():
            query = db.session.query(
                Inventory, PackingList
            ).join(
                PackingList, Inventory.packing_no == PackingList.packing_no
            )
            conditions = []
            if form.packing_no.data:
                conditions.append(Inventory.packing_no.ilike(f"%{form.packing_no.data}%"))
            if form.purchase_order_no.data:
                conditions.append(PackingList.purchase_order_no.ilike(f"%{form.purchase_order_no.data}%"))
            if form.parent_item_name.data:
                conditions.append(PackingList.parent_item_name.ilike(f"%{form.parent_item_name.data}%"))
            if form.child_item_name.data:
                conditions.append(Inventory.child_item_name.ilike(f"%{form.child_item_name.data}%"))
            if form.child_item_code.data:
                conditions.append(Inventory.child_item_code.ilike(f"%{form.child_item_code.data}%"))

            if conditions:
                rows = query.filter(or_(*conditions)).order_by(
                    Inventory.child_item_code, Inventory.batch_or_serial_no
                ).all()
                for inv, pack in rows:
                    results.append({
                        'child_item_code': inv.child_item_code,
                        'batch_or_serial_no': inv.batch_or_serial_no,
                        'packing_no': inv.packing_no,
                        'child_item_name': inv.child_item_name or '',
                        'expiration_date': inv.expiration_date.strftime('%Y-%m-%d') if inv.expiration_date else '',
                        'quantity': float(inv.quantity) if inv.quantity else 0,
                        'unit': inv.unit,
                        'test_quantity': inv.test_quantity,
                        'storage_temperature_c': float(inv.storage_temperature_c) if inv.storage_temperature_c else '',
                        'storage_location': inv.storage_location or '',
                        'has_toxic_chemical': inv.has_toxic_chemical,
                        'received_by': inv.received_by or '',
                        'issue_date': inv.issue_date.strftime('%Y-%m-%d') if inv.issue_date else '',
                    })
                if not results:
                    flash("查無相關資料", "danger")
            else:
                flash("請至少填寫一個搜尋條件", "warning")

    if request.method == 'POST' and 'update' in request.form:
        try:
            updated = 0
            codes = request.form.getlist('child_item_code[]')
            batches = request.form.getlist('batch_or_serial_no[]')
            child_names = request.form.getlist('child_item_name[]')
            quantities = request.form.getlist('quantity[]')
            units = request.form.getlist('unit[]')
            test_qtys = request.form.getlist('test_quantity[]')
            exp_dates = request.form.getlist('expiration_date[]')
            temps = request.form.getlist('storage_temperature_c[]')
            locations = request.form.getlist('storage_location[]')
            toxics = request.form.getlist('has_toxic_chemical[]')
            received_bys = request.form.getlist('received_by[]')
            issue_dates = request.form.getlist('issue_date[]')

            for i in range(len(codes)):
                inv = _get_inventory(codes[i], batches[i])
                if inv:
                    inv.child_item_name = child_names[i] if child_names[i] else None
                    inv.quantity = float(quantities[i]) if quantities[i] else 0
                    inv.unit = units[i]
                    inv.test_quantity = int(test_qtys[i]) if test_qtys[i] else 0
                    inv.expiration_date = (datetime.strptime(exp_dates[i], '%Y-%m-%d').date()
                                          if exp_dates[i] else None)
                    inv.storage_temperature_c = float(temps[i]) if temps[i] else None
                    inv.storage_location = locations[i] if locations[i] else None
                    inv.has_toxic_chemical = (f"{codes[i]}|{batches[i]}") in toxics
                    inv.received_by = received_bys[i] if received_bys[i] else None
                    inv.issue_date = (datetime.strptime(issue_dates[i], '%Y-%m-%d').date()
                                     if issue_dates[i] else None)
                    updated += 1

            db.session.commit()
            flash(f"成功更新 {updated} 筆資料", "success")
            return redirect(url_for(".index"))
        except Exception as e:
            db.session.rollback()
            flash(f"更新失敗：{str(e)}", "danger")

    return render_template("update_data.html", title="更新資料", form=form, results=results)


# ─── 取貨單 ────────────────────────────────────────────────────
@pages.route("/withdrawal", methods=["GET", "POST"])
@login_required
def create_withdrawal():
    form = WithdrawalForm()
    if form.validate_on_submit():
        inv = _get_inventory(form.child_item_code.data, form.batch_or_serial_no.data)
        if not inv:
            flash("找不到對應的庫存項目（請確認品項貨號與批號）", "danger")
            return redirect(url_for(".create_withdrawal"))
        if float(inv.quantity) < form.withdrawal_quantity.data:
            flash(f"庫存數量不足。目前庫存：{inv.quantity} {inv.unit}", "danger")
            return redirect(url_for(".create_withdrawal"))

        w = Withdrawal(
            child_item_code=form.child_item_code.data,
            batch_or_serial_no=form.batch_or_serial_no.data,
            withdrawal_quantity=form.withdrawal_quantity.data,
            withdrawal_date=form.withdrawal_date.data,
            requester=form.requester.data,
            purpose=form.purpose.data,
            status='pending'
        )
        db.session.add(w)
        db.session.commit()
        flash("取貨申請已提交，等待審核", "success")
        return redirect(url_for(".withdrawal_list"))
    return render_template("withdrawal.html", title="建立取貨單", form=form)


@pages.route("/withdrawals", methods=["GET"])
@login_required
def withdrawal_list():
    withdrawals = db.session.query(
        Withdrawal, Inventory, PackingList
    ).join(
        Inventory,
        (Withdrawal.child_item_code == Inventory.child_item_code) &
        (Withdrawal.batch_or_serial_no == Inventory.batch_or_serial_no)
    ).join(
        PackingList, Inventory.packing_no == PackingList.packing_no
    ).filter(
        Withdrawal.requester == session.get('name')
    ).order_by(Withdrawal.created_at.desc()).all()

    data = []
    for w, inv, pack in withdrawals:
        data.append({
            'id': w.id,
            'child_item_code': inv.child_item_code,
            'batch_or_serial_no': inv.batch_or_serial_no,
            'packing_no': inv.packing_no,
            'child_item_name': inv.child_item_name,
            'withdrawal_quantity': float(w.withdrawal_quantity),
            'unit': inv.unit,
            'withdrawal_date': w.withdrawal_date,
            'requester': w.requester,
            'purpose': w.purpose,
            'status': w.status,
            'created_at': w.created_at,
        })
    return render_template("withdrawal_list.html", title="我的取貨單", withdrawals=data)


# ─── 審核 ──────────────────────────────────────────────────────
@pages.route("/approvals", methods=["GET"])
@approver_required
def approval_list():
    pending = db.session.query(
        Withdrawal, Inventory, PackingList
    ).join(
        Inventory,
        (Withdrawal.child_item_code == Inventory.child_item_code) &
        (Withdrawal.batch_or_serial_no == Inventory.batch_or_serial_no)
    ).join(
        PackingList, Inventory.packing_no == PackingList.packing_no
    ).filter(
        Withdrawal.status == 'pending'
    ).order_by(Withdrawal.created_at.asc()).all()

    data = []
    for w, inv, pack in pending:
        data.append({
            'id': w.id,
            'child_item_code': inv.child_item_code,
            'batch_or_serial_no': inv.batch_or_serial_no,
            'packing_no': inv.packing_no,
            'child_item_name': inv.child_item_name,
            'current_quantity': float(inv.quantity),
            'withdrawal_quantity': float(w.withdrawal_quantity),
            'unit': inv.unit,
            'withdrawal_date': w.withdrawal_date,
            'requester': w.requester,
            'purpose': w.purpose,
            'created_at': w.created_at,
        })
    return render_template("approval_list.html", title="待審核取貨單", withdrawals=data)


@pages.route("/approval/<int:withdrawal_id>", methods=["GET", "POST"])
@approver_required
def approve_withdrawal(withdrawal_id):
    w = Withdrawal.query.get_or_404(withdrawal_id)
    form = ApprovalForm()
    inv = _get_inventory(w.child_item_code, w.batch_or_serial_no)

    if form.validate_on_submit():
        approval = Approval(
            withdrawal_id=w.id,
            approver_email=session.get('email'),
            approval_status=form.approval_status.data,
            approval_comment=form.approval_comment.data
        )
        w.status = form.approval_status.data
        if form.approval_status.data == 'approved':
            inv.quantity = float(inv.quantity) - float(w.withdrawal_quantity)
            flash("取貨單已批准，庫存已更新", "success")
        else:
            flash("取貨單已駁回", "info")
        db.session.add(approval)
        db.session.commit()
        return redirect(url_for(".approval_list"))

    return render_template(
        "approval.html", title="審核取貨單",
        form=form, withdrawal=w, inventory=inv
    )