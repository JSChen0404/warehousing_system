from datetime import datetime, timezone
from warehousing_system import db


class User(db.Model):
    """使用者表"""
    __tablename__ = 'users'
    __table_args__ = {'schema': 'warehousing'}
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_approver = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<User {self.email}>'


class ProductCatalog(db.Model):
    """產品目錄表 - parent_item_name → 多個 child_item_name"""
    __tablename__ = 'product_catalog'
    __table_args__ = {'schema': 'warehousing'}
    
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    parent_item_name = db.Column('parent_item_name', db.Text, nullable=False)
    child_item_name = db.Column('child_item_name', db.Text, nullable=False)
    created_at = db.Column('created_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column('updated_at', db.DateTime,
                          default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<ProductCatalog {self.parent_item_name} - {self.child_item_name}>'


class PackingList(db.Model):
    """裝箱單表"""
    __tablename__ = 'packing_list'
    __table_args__ = {'schema': 'warehousing'}
    
    packing_no = db.Column('packing_no', db.Text, primary_key=True)
    arrival_date = db.Column('arrival_date', db.Date)
    purchase_order_no = db.Column('purchase_order_no', db.Text)
    parent_item_name = db.Column('parent_item_name', db.Text)
    experiment_category = db.Column('experiment_category', db.Text)
    parent_item_code = db.Column('parent_item_code', db.Text)
    
    items = db.relationship('Inventory', backref='packing_list', lazy=True)
    
    def __repr__(self):
        return f'<PackingList {self.packing_no}>'


class Inventory(db.Model):
    """庫存表 - 複合主鍵 (child_item_code, batch_or_serial_no)"""
    __tablename__ = 'inventory'
    __table_args__ = {'schema': 'warehousing'}
    
    child_item_code = db.Column('child_item_code', db.Text, primary_key=True)
    batch_or_serial_no = db.Column('batch_or_serial_no', db.Text, primary_key=True)
    
    packing_no = db.Column('packing_no', db.Text,
                          db.ForeignKey('warehousing.packing_list.packing_no'), nullable=False)
    child_item_name = db.Column('child_item_name', db.Text)
    expiration_date = db.Column('expiration_date', db.Date)
    quantity = db.Column('quantity', db.Numeric)
    unit = db.Column('unit', db.Text)
    test_quantity = db.Column('test_quantity', db.Integer)
    storage_temperature_c = db.Column('storage_temperature_c', db.Numeric)
    storage_location = db.Column('storage_location', db.Text)
    has_toxic_chemical = db.Column('has_toxic_chemical', db.Boolean, default=False)
    received_by = db.Column('received_by', db.Text)
    issue_date = db.Column('issue_date', db.Date)
    
    withdrawals = db.relationship('Withdrawal', backref='inventory_item', lazy=True)
    
    def __repr__(self):
        return f'<Inventory {self.child_item_code} / {self.batch_or_serial_no}>'


class Withdrawal(db.Model):
    """取貨單表"""
    __tablename__ = 'withdrawal'
    
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    child_item_code = db.Column('child_item_code', db.Text, nullable=False)
    batch_or_serial_no = db.Column('batch_or_serial_no', db.Text, nullable=False)
    withdrawal_quantity = db.Column('withdrawal_quantity', db.Numeric, nullable=False)
    withdrawal_date = db.Column('withdrawal_date', db.Date, nullable=False)
    requester = db.Column('requester', db.Text, nullable=False)
    purpose = db.Column('purpose', db.Text)
    status = db.Column('status', db.String(20), default='pending')
    created_at = db.Column('created_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    approval = db.relationship('Approval', backref='withdrawal', uselist=False, lazy=True)
    
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['child_item_code', 'batch_or_serial_no'],
            ['warehousing.inventory.child_item_code', 'warehousing.inventory.batch_or_serial_no']
        ),
        {'schema': 'warehousing'}
    )
    
    def __repr__(self):
        return f'<Withdrawal {self.id}>'


class Approval(db.Model):
    """審核記錄表"""
    __tablename__ = 'approval'
    __table_args__ = {'schema': 'warehousing'}
    
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    withdrawal_id = db.Column('withdrawal_id', db.Integer,
                             db.ForeignKey('warehousing.withdrawal.id'), nullable=False)
    approver_email = db.Column('approver_email', db.String(120), nullable=False)
    approval_status = db.Column('approval_status', db.String(20), nullable=False)
    approval_comment = db.Column('approval_comment', db.Text)
    approval_date = db.Column('approval_date', db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Approval {self.id}>'