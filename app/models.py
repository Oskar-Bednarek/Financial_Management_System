from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKeyConstraint

db = SQLAlchemy()

class Project(db.Model):
    __tablename__ = 'projects'
    ProjectID = db.Column(db.Integer, primary_key=True)
    ProjectName = db.Column(db.String(100), nullable=False)
    StartDate = db.Column(db.Date, nullable=False)
    EndDate = db.Column(db.Date, nullable=True)
    Status = db.Column(db.String(50))

    loans = db.relationship('Loan', backref='project', lazy=True)


class Loan(db.Model):
    __tablename__ = 'loans'
    LoanNumber = db.Column(db.Integer, primary_key=True)
    ProjectType = db.Column(db.String(50))
    StartDate = db.Column(db.Date, nullable=False)
    TotalAmount = db.Column(db.Float, nullable=False, default=0)
    InterestRate = db.Column(db.Float, nullable=False)
    Capitalization = db.Column(db.Boolean, default=False)

    ProjectID = db.Column(db.Integer, db.ForeignKey('projects.ProjectID'), nullable=True)

    tranches = db.relationship('Tranche', backref='loan', lazy=True, overlaps="repayments,adjustments")
    repayments = db.relationship('Repayment', back_populates='loan', lazy=True, overlaps="tranche,repayments")
    adjustments = db.relationship('Adjustment', back_populates='loan', lazy=True, overlaps="tranche,adjustments")


class Tranche(db.Model):
    __tablename__ = 'tranches'
    TrancheID = db.Column(db.Integer, primary_key=True)
    TrancheNumber = db.Column(db.Integer, nullable=False)
    LoanNumber = db.Column(db.Integer, db.ForeignKey('loans.LoanNumber'), nullable=False)
    Amount = db.Column(db.Float, nullable=False)
    DateReceived = db.Column(db.Date, nullable=False)
    FullRepayment = db.Column(db.Boolean, default=False)

    adjustments = db.relationship('Adjustment', back_populates='tranche', overlaps="loan,adjustments")
    repayments = db.relationship('Repayment', back_populates='tranche', overlaps="loan,repayments")

    __table_args__ = (
        db.UniqueConstraint('LoanNumber', 'TrancheNumber', name='uq_loan_tranche'),
    )


class Repayment(db.Model):
    __tablename__ = 'repayments'
    RepaymentID = db.Column(db.Integer, primary_key=True)
    LoanNumber = db.Column(db.Integer, db.ForeignKey('loans.LoanNumber'), nullable=False)
    TrancheNumber = db.Column(db.Integer, nullable=False)
    AmountPaid = db.Column(db.Float, nullable=False)
    DatePaid = db.Column(db.Date, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ['LoanNumber', 'TrancheNumber'],
            ['tranches.LoanNumber', 'tranches.TrancheNumber']
        ),
    )

    tranche = db.relationship(
        'Tranche',
        primaryjoin="and_(Repayment.LoanNumber==Tranche.LoanNumber, Repayment.TrancheNumber==Tranche.TrancheNumber)",
        back_populates='repayments',
        overlaps="loan"
    )

    loan = db.relationship('Loan', back_populates='repayments', overlaps="tranche")


class Adjustment(db.Model):
    __tablename__ = 'adjustments'
    AdjustmentID = db.Column(db.Integer, primary_key=True)
    TrancheNumber = db.Column(db.Integer, nullable=False)
    LoanNumber = db.Column(db.Integer, db.ForeignKey('loans.LoanNumber'), nullable=False)
    Date = db.Column(db.Date, nullable=False)
    Amount = db.Column(db.Numeric(precision=12, scale=2), nullable=False)
    Description = db.Column(db.String(200))

    tranche = db.relationship(
        'Tranche',
        primaryjoin="and_(Adjustment.LoanNumber==Tranche.LoanNumber, Adjustment.TrancheNumber==Tranche.TrancheNumber)",
        back_populates='adjustments',
        overlaps="loan"
    )

    loan = db.relationship('Loan', back_populates='adjustments', overlaps="tranche")

    __table_args__ = (
        ForeignKeyConstraint(
            ['LoanNumber', 'TrancheNumber'],
            ['tranches.LoanNumber', 'tranches.TrancheNumber']
        ),
    )
