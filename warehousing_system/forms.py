from flask_wtf import FlaskForm
from wtforms import (StringField, IntegerField, FloatField, DateField,
                     SubmitField, PasswordField, SelectField, TextAreaField, BooleanField, HiddenField)
from wtforms.validators import DataRequired, Length, NumberRange, EqualTo, Email, Optional


class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField(
        'Password',
        validators=[DataRequired(), Length(min=4, message='Password must be at least 4 characters.')]
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match.')]
    )
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    email = StringField('Account', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class PackingListForm(FlaskForm):
    """裝箱單 + 貨物層級表單 (Step 1)"""
    parent_item_name = SelectField('主貨物名稱', validators=[DataRequired()], choices=[])
    experiment_category = StringField('實驗類別', validators=[Optional()])
    arrival_date = DateField('到貨日', format='%Y-%m-%d', validators=[DataRequired()])
    packing_no = StringField('裝箱單號', validators=[DataRequired()])
    purchase_order_no = StringField('採購單號 (NCMO)', validators=[Optional()])
    parent_item_code = StringField('主貨物代號', validators=[Optional()])
    submit = SubmitField('下一步：填寫品項明細')


class SearchForm(FlaskForm):
    """多條件搜尋表單"""
    packing_no = StringField('裝箱單號', validators=[Optional()])
    purchase_order_no = StringField('採購單號', validators=[Optional()])
    parent_item_name = StringField('主貨物名稱', validators=[Optional()])
    parent_item_code = StringField('主貨物代號', validators=[Optional()])
    child_item_code = StringField('子貨物代號', validators=[Optional()])
    batch_or_serial_no = StringField('批號/序列號', validators=[Optional()])
    submit = SubmitField('搜尋')


class UpdateQuantityForm(FlaskForm):
    """搜尋要更新的資料"""
    packing_no = StringField('裝箱單號', validators=[Optional()])
    purchase_order_no = StringField('採購單號', validators=[Optional()])
    parent_item_name = StringField('主貨物名稱', validators=[Optional()])
    child_item_name = StringField('子貨物名稱', validators=[Optional()])
    child_item_code = StringField('子貨物代號', validators=[Optional()])
    submit = SubmitField('搜尋')


class WithdrawalForm(FlaskForm):
    """取貨單表單"""
    batch_or_serial_no = StringField('批號/序列號', validators=[DataRequired()])
    child_item_name = StringField('子貨物名稱', validators=[Optional()])   # 自動填入，顯示用
    child_item_code = HiddenField()                                         # 由 JS 自動填入
    withdrawal_quantity = FloatField('取貨數量', validators=[DataRequired(), NumberRange(min=0)])
    withdrawal_date = DateField('取貨日期', format='%Y-%m-%d', validators=[DataRequired()])
    requester = StringField('申請人', validators=[DataRequired()])
    purpose = TextAreaField('用途說明', validators=[DataRequired()])
    submit = SubmitField('提交取貨申請')


class ApprovalForm(FlaskForm):
    """審核表單"""
    approval_status = SelectField(
        '審核結果',
        choices=[('approved', '批准'), ('rejected', '駁回')],
        validators=[DataRequired()]
    )
    approval_comment = TextAreaField('審核意見', validators=[Optional()])
    submit = SubmitField('提交審核')