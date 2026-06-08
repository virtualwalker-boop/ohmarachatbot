from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

async def generate_quotation_pdf(booking_id: int) -> str:
    """
    Generates a PDF Quotation using ReportLab and returns the file path.
    """
    os.makedirs("output_pdfs", exist_ok=True)
    filename = f"output_pdfs/quotation_{booking_id}.pdf"
    
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, f"Quotation for Booking #{booking_id}")
    c.drawString(100, 730, "Total Amount: $100.00 (Mock)")
    c.drawString(100, 710, "Thank you for your business.")
    c.save()
    
    return filename
