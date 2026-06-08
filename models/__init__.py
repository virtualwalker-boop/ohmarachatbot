from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base

class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True, index=True)
    fb_psid = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    contact_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    bookings = relationship("Booking", back_populates="customer")

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'))
    status = Column(String, default="PENDING") # PENDING, CONFIRMED, DIAGNOSED, IN_PROGRESS, CLOSED
    service_type = Column(String, nullable=False) # HOME_SERVICE, DROP_OFF
    appliance_category = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    model = Column(String, nullable=True)
    symptom = Column(String, nullable=True)
    address = Column(String, nullable=True)
    landmark = Column(String, nullable=True)
    estimated_cost_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    customer = relationship("Customer", back_populates="bookings")
    quotation = relationship("Quotation", back_populates="booking", uselist=False)

class Quotation(Base):
    __tablename__ = 'quotations'
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey('bookings.id'))
    total_amount = Column(Float, nullable=False)
    pdf_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    booking = relationship("Booking", back_populates="quotation")
    transaction = relationship("Transaction", back_populates="quotation", uselist=False)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey('quotations.id'))
    stripe_session_id = Column(String, nullable=True)
    status = Column(String, default="PENDING") # PENDING, SUCCESS, FAILED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    quotation = relationship("Quotation", back_populates="transaction")
