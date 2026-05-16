"""
ColxPath — unified design system
All QSS lives here so every window shares the same tokens.
"""

# ── Colour palette ─────────────────────────────────────────────────────────────
C = {
    "ink":        "#0D1B2A",   # near-black text
    "ink_mid":    "#3D5166",   # secondary text
    "ink_soft":   "#8497A8",   # muted / placeholder
    "surface":    "#F4F7FA",   # app background
    "card":       "#FFFFFF",   # card / panel
    "border":     "#DDE3EA",   # default border
    "border_focus": "#8a40d4", # input focus ring

    "primary":    "#791ad8",   # brand blue
    "primary_dk": "#61249e",   # hover
    "primary_lt": "#EEF3FD",   # tinted bg

    "success":    "#059669",
    "success_lt": "#D1FAE5",
    "danger":     "#DC2626",
    "danger_lt":  "#FEE2E2",
    "warning":    "#D97706",
    "warning_lt": "#FEF3C7",

    "nav_bg":     "#6626a6",   # dark sidebar / navbar
    "nav_text":   "#CBD5E1",
    "nav_active": "#FFFFFF",
}

FONT = "'DM Sans', 'Segoe UI', sans-serif"
FONT_MONO = "'JetBrains Mono', 'Consolas', monospace"

# ── Base stylesheet (applies globally) ────────────────────────────────────────
BASE_QSS = f"""
    * {{ font-family: {FONT}; }}

    /* ── Scrollbars ── */
    QScrollBar:vertical {{
        background: {C['surface']}; width: 8px; border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {C['border']}; border-radius: 4px; min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {C['ink_soft']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QScrollBar:horizontal {{
        background: {C['surface']}; height: 8px; border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {C['border']}; border-radius: 4px; min-width: 32px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {C['ink_soft']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ── Tooltip ── */
    QToolTip {{
        background: {C['ink']}; color: #FFFFFF;
        border: none; border-radius: 4px;
        font-size: 12px; padding: 4px 8px;
    }}

    /* ── Shared object names ── */

    #navbar {{
        background: {C['nav_bg']};
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }}
    #navBrand {{
        font-size: 17px; font-weight: 700;
        color: {C['nav_active']}; letter-spacing: 0.3px;
    }}
    #navBrandSub {{
        font-size: 10px; font-weight: 500;
        color: rgba(203,213,225,0.55); letter-spacing: 1.5px;
        text-transform: uppercase;
    }}
    #navDoctor {{
        font-size: 12px; color: {C['nav_text']};
    }}
    #navTitle {{
        font-size: 14px; font-weight: 600;
        color: {C['nav_active']}; letter-spacing: 0.2px;
    }}
    #backBtn {{
        background: none; border: none;
        color: {C['nav_text']}; font-size: 13px; font-weight: 500;
        padding: 0 4px;
    }}
    #backBtn:hover {{ color: {C['nav_active']}; }}

    #logoutBtn {{
        background: rgba(255,255,255,0.07);
        color: {C['nav_text']};
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 6px; font-size: 12px; font-weight: 500;
        padding: 0 12px;
    }}
    #logoutBtn:hover {{
        background: rgba(220,38,38,0.18);
        color: #FCA5A5;
        border-color: rgba(220,38,38,0.3);
    }}

    #pageTitle {{
        font-size: 20px; font-weight: 700; color: {C['ink']};
    }}
    #greeting {{
        font-size: 28px; font-weight: 700; color: {C['ink']};
        letter-spacing: -0.5px;
    }}
    #subtitle {{
        font-size: 14px; color: {C['ink_soft']};
    }}

    /* ── Panels ── */
    #panel {{
        background: {C['card']};
        border: 1px solid {C['border']};
        border-radius: 12px;
    }}
    #subPanel {{
        background: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 8px;
    }}

    /* ── Form elements ── */
    #fieldLabel {{
        font-size: 12px; font-weight: 600;
        color: {C['ink_mid']}; letter-spacing: 0.2px;
    }}
    #formInput {{
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 0 12px;
        font-size: 14px;
        color: {C['ink']};
        background: {C['card']};
        selection-background-color: {C['primary_lt']};
    }}
    #formInput:focus {{
        border-color: {C['primary']};
        background: {C['card']};
        outline: none;
    }}
    QComboBox#formInput {{
        padding-left: 10px;
    }}
    QComboBox#formInput::drop-down {{
        border: none; width: 26px;
        subcontrol-origin: padding;
        subcontrol-position: right center;
    }}
    QComboBox#formInput QAbstractItemView {{
        background: {C['card']};
        border: 1px solid {C['border']};
        border-radius: 6px;
        selection-background-color: {C['primary_lt']};
        color: {C['ink']};
        padding: 4px;
    }}

    /* ── Buttons ── */
    #primaryBtn {{
        background: {C['primary']};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-size: 13px; font-weight: 600;
        padding: 0 16px;
        letter-spacing: 0.1px;
    }}
    #primaryBtn:hover {{ background: {C['primary_dk']}; }}
    #primaryBtn:pressed {{ background: #521e85; }}
    #primaryBtn:disabled {{ background: #93B4F0; color: rgba(255,255,255,0.6); }}

    #analyzeBtn {{
        background: {C['success']};
        color: #FFFFFF; border: none;
        border-radius: 8px;
        font-size: 13px; font-weight: 600;
        padding: 0 16px;
    }}
    #analyzeBtn:hover {{ background: #047857; }}
    #analyzeBtn:disabled {{ background: #6EE7B7; color: rgba(255,255,255,0.7); }}

    #secondaryBtn {{
        background: {C['card']};
        color: {C['ink_mid']};
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        font-size: 13px; font-weight: 500;
        padding: 0 16px;
    }}
    #secondaryBtn:hover {{
        background: {C['surface']};
        border-color: {C['primary']};
        color: {C['primary']};
    }}

    #linkBtn {{
        background: none; border: none;
        color: {C['primary']};
        font-size: 13px; font-weight: 600;
        padding: 0 4px;
    }}
    #linkBtn:hover {{ color: {C['primary_dk']}; }}

    #dangerBtn {{
        background: {C['danger_lt']};
        color: {C['danger']};
        border: 1px solid #FECACA;
        border-radius: 8px;
        font-size: 12px; font-weight: 600;
        padding: 0 12px;
    }}
    #dangerBtn:hover {{ background: {C['danger']}; color: white; border-color: {C['danger']}; }}

    /* ── Section labels ── */
    #sectionLabel {{
        font-size: 10px; font-weight: 700;
        color: {C['primary']};
        letter-spacing: 1px;
        text-transform: uppercase;
    }}

    /* ── Tables ── */
    #historyTable, #patientTable {{
        border: 1px solid {C['border']};
        border-radius: 10px;
        gridline-color: #EEF2F6;
        font-size: 13px;
        background: {C['card']};
        alternate-background-color: {C['surface']};
    }}
    QHeaderView::section {{
        background: {C['surface']};
        color: {C['ink_mid']};
        font-weight: 700;
        font-size: 11px;
        letter-spacing: 0.5px;
        padding: 10px 12px;
        border: none;
        border-bottom: 2px solid {C['border']};
        text-transform: uppercase;
    }}
    QTableWidget::item {{
        padding: 6px 10px;
        color: {C['ink']};
    }}
    QTableWidget::item:selected {{
        background: {C['primary_lt']};
        color: {C['primary_dk']};
    }}

    /* ── Search / filter inputs ── */
    #searchInput {{
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 0 14px;
        font-size: 13px;
        background: {C['card']};
        color: {C['ink']};
    }}
    #searchInput:focus {{ border-color: {C['primary']}; }}

    #filterCombo {{
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        padding: 0 10px;
        font-size: 13px;
        background: {C['card']};
        color: {C['ink']};
    }}

    /* ── Footer ── */
    #footer {{
        background: {C['nav_bg']};
        border-top: 1px solid rgba(255,255,255,0.06);
    }}
    #footerText {{
        font-size: 11px;
        color: rgba(203,213,225,0.4);
        letter-spacing: 0.3px;
    }}

    /* ── Misc ── */
    #mutedText {{ color: {C['ink_soft']}; font-size: 13px; }}
    #hintText  {{ font-size: 12px; color: {C['ink_soft']}; }}

    #patientDisplay {{
        font-size: 13px; color: {C['ink']};
        line-height: 1.5;
    }}
    #metricKey {{
        font-size: 12px; color: {C['ink_soft']};
    }}
    #metricVal {{
        font-size: 13px; font-weight: 600; color: {C['ink']};
    }}
    #notesEdit {{
        border: 1.5px solid {C['border']};
        border-radius: 8px;
        font-size: 13px;
        padding: 8px;
        background: {C['card']};
        color: {C['ink']};
    }}
    #notesEdit:focus {{ border-color: {C['primary']}; }}

    #imgFrame {{
        background: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 8px;
    }}
    #imgPlaceholder {{
        color: {C['ink_soft']};
        font-size: 12px;
    }}
    #imgCaption {{
        font-size: 10px; color: {C['ink_soft']};
        font-weight: 600; letter-spacing: 0.5px;
        text-transform: uppercase;
    }}
"""

# ── Auth-screen QSS (brand panel + form panel) ─────────────────────────────────
AUTH_QSS = BASE_QSS + f"""
    QWidget {{  }}

    #brandPanel {{
        background: {C['nav_bg']};
    }}
    #brandTitle {{
        color: #FFFFFF;
        font-size: 30px; font-weight: 700;
        letter-spacing: -0.5px;
    }}
    #brandTagline {{
        color: rgba(203,213,225,0.65);
        font-size: 14px; line-height: 1.7;
    }}
    #formPanel {{
        background: {C['card']};
    }}
    #formTitle {{
        font-size: 24px; font-weight: 700;
        color: {C['ink']}; letter-spacing: -0.3px;
    }}
    #formSubtitle {{
        font-size: 13px; color: {C['ink_soft']};
        margin-top: 2px;
    }}

    #dividerLine {{ 
        color: {C['border']};
        background: {C['nav_bg']};
    }}
"""

# ── Dialog QSS ─────────────────────────────────────────────────────────────────
DIALOG_QSS = BASE_QSS + f"""
    QDialog {{ background: {C['card']}; }}
    #dialogTitle {{
        font-size: 18px; font-weight: 700;
        color: {C['ink']}; letter-spacing: -0.2px;
    }}
    #separator {{ color: {C['border']}; }}
"""