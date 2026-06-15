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


def register_date_filters(templates) -> None:
    """Registra il filtro Jinja2 'it_date' per la formattazione localizzata delle date."""
    templates.env.filters["it_date"] = format_date_it
