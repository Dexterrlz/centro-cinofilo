"""Localizzazione italiana per nomi di giorni e mesi nelle date dei template."""

GIORNI_ITA = {
    "Monday": "Lunedì",
    "Tuesday": "Martedì",
    "Wednesday": "Mercoledì",
    "Thursday": "Giovedì",
    "Friday": "Venerdì",
    "Saturday": "Sabato",
    "Sunday": "Domenica",
}

GIORNI_BREVI_ITA = {
    "Mon": "Lun",
    "Tue": "Mar",
    "Wed": "Mer",
    "Thu": "Gio",
    "Fri": "Ven",
    "Sat": "Sab",
    "Sun": "Dom",
}

MESI_ITA = {
    "January": "Gennaio",
    "February": "Febbraio",
    "March": "Marzo",
    "April": "Aprile",
    "May": "Maggio",
    "June": "Giugno",
    "July": "Luglio",
    "August": "Agosto",
    "September": "Settembre",
    "October": "Ottobre",
    "November": "Novembre",
    "December": "Dicembre",
}

MESI_BREVI_ITA = {
    "Jan": "Gen",
    "Feb": "Feb",
    "Mar": "Mar",
    "Apr": "Apr",
    "May": "Mag",
    "Jun": "Giu",
    "Jul": "Lug",
    "Aug": "Ago",
    "Sep": "Set",
    "Oct": "Ott",
    "Nov": "Nov",
    "Dec": "Dic",
}


def format_date_it(value, fmt: str) -> str:
    """Formatta una data con strftime traducendo giorni e mesi in italiano."""
    text = value.strftime(fmt)
    for mapping in (GIORNI_ITA, MESI_ITA, GIORNI_BREVI_ITA, MESI_BREVI_ITA):
        for en, it in mapping.items():
            text = text.replace(en, it)
    return text


STATUS_LABELS_IT = {
    "pending": "In attesa",
    "confirmed": "Confermata",
    "cancelled": "Cancellata",
    "completed": "Completata",
    "no_show": "Assente",
}


def format_date_long(value) -> str:
    """Formatta una data come 'Lunedì 28 Giugno 2026'."""
    giorno = GIORNI_ITA.get(value.strftime("%A"), value.strftime("%A"))
    mese = MESI_ITA.get(value.strftime("%B"), value.strftime("%B"))
    return f"{giorno} {value.day} {mese} {value.year}"


def format_status_label(value) -> str:
    raw = value.value if hasattr(value, "value") else str(value)
    return STATUS_LABELS_IT.get(raw, raw)


def register_date_filters(templates) -> None:
    """Registra i filtri Jinja2 per la formattazione localizzata."""
    templates.env.filters["it_date"] = format_date_it
    templates.env.filters["data_lunga"] = format_date_long
    templates.env.filters["format_date_long"] = format_date_long
    templates.env.filters["stato_label"] = format_status_label
    templates.env.filters["status_label"] = format_status_label
