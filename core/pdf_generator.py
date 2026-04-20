"""
PDF report generator for PathoVision.
Requires: reportlab  (pip install reportlab)
"""
import os
from datetime import datetime


def generate_patient_report(patient: dict, analyses: list, output_path: str = None) -> str:
    """
    Generate a PDF report for a patient and save it to their folder.
    Returns the path to the generated PDF.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise ImportError("reportlab is required: pip install reportlab")

    if output_path is None:
        folder = patient.get("folder_path", "")
        if folder:
            output_path = os.path.join(folder, "report.pdf")
        else:
            output_path = f"patient_{patient['id']}_report.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    W, H = A4

    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#1A5276"),
        spaceAfter=4
    )
    heading_style = ParagraphStyle(
        "Heading", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#2E86C1"),
        spaceBefore=14, spaceAfter=4
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#2C3E50"),
        spaceAfter=4
    )

    story = []

    # ── Header ────────────────────────────────────────────────────
    story.append(Paragraph("🔬  PathoVision", title_style))
    story.append(Paragraph("AI-Powered Cancer Detection Platform", body_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2E86C1")))
    story.append(Spacer(1, 0.4*cm))

    gen_date = datetime.now().strftime("%B %d, %Y  %H:%M")
    story.append(Paragraph(f"<b>Report Generated:</b> {gen_date}", body_style))
    story.append(Spacer(1, 0.5*cm))

    # ── Patient info ──────────────────────────────────────────────
    story.append(Paragraph("Patient Information", heading_style))

    info_data = [
        ["Full Name", f"{patient.get('first_name','')} {patient.get('last_name','')}"],
        ["Age", str(patient.get("age") or "—")],
        ["Sex", patient.get("sexe") or "—"],
        ["Tissue", patient.get("tissue") or "—"],
        ["Marker (Marqueur)", patient.get("marqueur") or "—"],
        ["Patient Since", (patient.get("created_at") or "")[:10] or "—"],
    ]

    info_table = Table(info_data, colWidths=[5*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EBF5FB")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1A5276")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F7FBFE")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5D8DC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.6*cm))

    # ── Analyses ─────────────────────────────────────────────────
    story.append(Paragraph("Analysis History", heading_style))

    if not analyses:
        story.append(Paragraph("No analyses recorded for this patient.", body_style))
    else:
        headers = ["Date", "Type", "Result", "Confidence", "DAB%", "Regions", "Mean Int.", "Doctor"]
        rows = [headers]
        for a in analyses:
            prob = a.get("result_prob")
            conf = f"{prob*100:.1f}%" if prob is not None else "—"
            dab  = a.get("dab_coverage")
            dab_s = f"{dab:.2f}%" if dab is not None else "—"
            mi = a.get("mean_intensity")
            mi_s = f"{mi:.1f}" if mi is not None else "—"
            rows.append([
                (a.get("created_at") or "")[:16],
                a.get("analysis_type") or "—",
                a.get("result_label") or "—",
                conf, dab_s,
                str(a.get("dab_regions") or "—"),
                mi_s,
                a.get("doctor_name") or "—"
            ])

        col_widths = [3.2*cm, 2.4*cm, 3.4*cm, 2.4*cm, 2*cm, 2*cm, 2.4*cm, 3.2*cm]
        a_table = Table(rows, colWidths=col_widths, repeatRows=1)
        a_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FBFE")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5D8DC")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        # Colour Pathologique red, Non Pathologique green
        for i, a in enumerate(analyses, start=1):
            label = a.get("result_label", "")
            if label == "Pathologique":
                a_style.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#C0392B")))
                a_style.append(("FONTNAME", (2, i), (2, i), "Helvetica-Bold"))
            elif label == "Non Pathologique":
                a_style.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#1E8449")))
                a_style.append(("FONTNAME", (2, i), (2, i), "Helvetica-Bold"))
        a_table.setStyle(TableStyle(a_style))
        story.append(a_table)

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D5D8DC")))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "This report was generated automatically by PathoVision. "
        "It is intended to assist medical professionals and does not replace clinical judgment.",
        ParagraphStyle("Disclaimer", parent=styles["Normal"],
                       fontSize=8, textColor=colors.HexColor("#AAB7B8"),
                       alignment=TA_CENTER)
    ))

    doc.build(story)
    return output_path