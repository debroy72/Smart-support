# backend/pdf_report.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

def generate_summary_pdf(data, out_path="backend/report.pdf"):
    """
    data: dict from /analyze API response
    out_path: PDF file path to write
    """
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    title = ParagraphStyle('TitleCenter', parent=styles['Title'], alignment=TA_CENTER)

    story.append(Paragraph("SmartSupport — Log Analysis Report", title))
    story.append(Spacer(1, 12))
    story.append(Paragraph(datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), styles['Normal']))
    story.append(Spacer(1, 20))

    # Summary
    story.append(Paragraph("<b>Summary</b>", styles['Heading2']))
    summary = data.get("summary", {})
    story.append(Paragraph(summary.get("headline", "No summary available."), styles['Normal']))
    story.append(Spacer(1, 12))

    # Totals
    totals = data.get("totals", {})
    t_data = [["Level", "Count"]] + [[k, str(v)] for k, v in totals.items()]
    table = Table(t_data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    story.append(table)
    story.append(Spacer(1, 20))

    # Incidents
    incidents = data.get("incidents", [])
    if incidents:
        story.append(Paragraph("<b>Incidents</b>", styles['Heading2']))
        i_data = [["Label", "Severity", "Count", "Root Cause"]]
        for inc in incidents[:8]:  # top 8 only
            i_data.append([inc["label"], inc["severity"], str(inc["count"]), inc["root_cause"]])
        i_table = Table(i_data, hAlign='LEFT')
        i_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(i_table)
        story.append(Spacer(1, 20))

    # Recommendations
    story.append(Paragraph("<b>Recommendations</b>", styles['Heading2']))
    recs = []
    for inc in incidents[:5]:
        recs.extend(inc.get("recommend", []))
    if recs:
        for r in recs:
            story.append(Paragraph(f"• {r}", styles['Normal']))
    else:
        story.append(Paragraph("No recommendations found.", styles['Normal']))

    doc.build(story)
    return out_path